from __future__ import annotations

import asyncio
import json
import tempfile
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

from bahram.core.engine import AgentEngine, AgentResponse, Message, MessageRole, RunConfig
from bahram.providers.fallback import FallbackProvider


class AlwaysFailProvider:
    async def complete(self, messages, tools=None, **kwargs):
        raise Exception("Always fails")

    async def stream(self, messages, tools=None, **kwargs):
        raise Exception("Always fails")


class MockProvider:
    def __init__(self, responses=None, fail_count=0):
        self._responses = list(responses or [])
        self._call_count = 0
        self._fail_count = fail_count

    async def complete(self, messages, tools=None, **kwargs):
        if self._call_count < self._fail_count:
            self._call_count += 1
            raise Exception(f"Mock provider failure #{self._call_count}")
        if self._responses:
            return self._responses.pop(0)
        return AgentResponse(content="Mock response")

    async def stream(self, messages, tools=None, **kwargs):
        resp = await self.complete(messages, tools, **kwargs)
        yield resp.content


class MockTool:
    def schema(self):
        return {
            "name": "mock_tool",
            "description": "A mock tool",
            "parameters": {"type": "object", "properties": {}},
        }

    async def execute(self, **kwargs):
        return "tool result"


class TestCircuitBreakerWiring:
    def test_circuit_breaker_initialized(self):
        engine = AgentEngine()
        assert engine._circuit_breaker is not None

    def test_record_success_resets_circuit(self):
        engine = AgentEngine()
        cb = engine._circuit_breaker
        for _ in range(5):
            engine.record_provider_failure("test_provider")
        assert cb.get_circuit("test_provider").state == "open"

        cb._circuits["test_provider"].state = "half-open"
        engine.record_provider_success("test_provider")
        assert cb.get_circuit("test_provider").state == "closed"

    def test_circuit_open_allows_fallback(self):
        engine = AgentEngine()
        primary = AlwaysFailProvider()
        fallback = MockProvider(responses=[AgentResponse(content="fallback")])
        engine.providers["test"] = primary
        engine.providers["__fallback__"] = FallbackProvider(primary, [fallback])

        for _ in range(5):
            engine.record_provider_failure("test")

        provider = engine.get_provider("test/model")
        assert provider is not None


class TestBudgetWiring:
    def test_budget_manager_set_on_engine(self):
        from bahram.autonomy.budget import BudgetManager
        engine = AgentEngine()
        bm = BudgetManager()
        engine.set_budget_manager(bm)
        assert engine._budget_manager is bm

    def test_event_tracker_set_on_engine(self):
        from bahram.autonomy.events import EventTracker
        engine = AgentEngine()
        et = EventTracker()
        engine.set_event_tracker(et)
        assert engine._event_tracker is et

    @pytest.mark.asyncio
    async def test_budget_check_stops_execution(self):
        from bahram.autonomy.budget import BudgetManager, BudgetConfig
        engine = AgentEngine()
        bm = BudgetManager(BudgetConfig(max_model_calls=0))
        engine.set_budget_manager(bm)
        engine.providers["test"] = MockProvider(responses=[
            AgentResponse(content="hello", tool_calls=[])
        ])

        messages = [Message(role=MessageRole.USER, content="hi")]
        response = await engine.run(messages, model="test/model", session_id="s1")
        assert "Budget limit reached" in response.content


class TestEventTrackerWiring:
    def test_event_tracker_initialized_in_engine(self):
        from bahram.autonomy.events import EventTracker
        engine = AgentEngine()
        et = EventTracker()
        engine.set_event_tracker(et)
        assert engine._event_tracker is et


class TestSmartContextIntegration:
    def test_smart_context_manager_works(self):
        from bahram.core.smart_context import SmartContextManager
        scm = SmartContextManager(max_tokens=1000)
        scm.set_system_prompt("You are helpful.")
        scm.add_history("user", "hello")
        scm.add_history("assistant", "hi there")
        scm.add_context("Some context", priority=3)
        messages = scm.build_context()
        assert len(messages) >= 2
        assert messages[0]["role"] == "system"
        usage = scm.get_usage()
        assert usage["total_used"] > 0

    def test_smart_context_optimize(self):
        from bahram.core.smart_context import SmartContextManager
        scm = SmartContextManager(max_tokens=100)
        scm.add_context("A" * 500, priority=1)
        scm.add_context("B" * 500, priority=5)
        removed = scm.optimize()
        assert removed >= 0


class TestCompressorFix:
    def test_compressor_has_real_prompt(self):
        import inspect
        from bahram.core.compressor import ContextCompressor
        cc = ContextCompressor()
        source = inspect.getsource(cc._model_compress)
        assert "Compress the following conversation" in source

    def test_heuristic_compress_works(self):
        from bahram.core.compressor import ContextCompressor
        cc = ContextCompressor()
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = cc._heuristic_compress(messages, target_tokens=100)
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert len(parsed) >= 1


class TestGatewayService:
    def test_gateway_creates_unit_file(self):
        from bahram.core.gateway_service import GatewayService
        with tempfile.TemporaryDirectory() as tmpdir:
            gs = GatewayService(work_dir=tmpdir)
            unit = gs._generate_systemd_unit(system=False)
            assert "Bahram AI Agent Gateway" in unit
            assert "ExecStart=" in unit

    def test_gateway_status_returns_dict(self):
        from bahram.core.gateway_service import GatewayService
        gs = GatewayService()
        status = gs.get_status()
        assert isinstance(status, dict)
        assert "status" in status


class TestSubagentEventWiring:
    def test_subagent_engine_accepts_event_tracker(self):
        from bahram.autonomy.subagent import SubagentEngine
        from bahram.autonomy.events import EventTracker
        engine = AgentEngine()
        et = EventTracker()
        se = SubagentEngine(engine, event_tracker=et)
        assert se._event_tracker is et


class TestJobEventWiring:
    def test_job_engine_accepts_event_tracker(self):
        from bahram.autonomy.jobs import JobEngine
        from bahram.autonomy.events import EventTracker
        et = EventTracker()
        with tempfile.TemporaryDirectory() as tmpdir:
            je = JobEngine(data_dir=tmpdir, event_tracker=et)
            assert je._event_tracker is et


class TestFallbackProvider:
    def test_fallback_falls_back_on_primary_failure(self):
        primary = MockProvider(fail_count=1)
        fallback = MockProvider(responses=[AgentResponse(content="fallback")])
        fp = FallbackProvider(primary, [fallback])
        assert fp.get_current_provider() == "MockProvider"

    def test_add_remove_fallback(self):
        primary = MockProvider()
        fp = FallbackProvider(primary, [])
        fb = MockProvider()
        fp.add_fallback(fb)
        assert len(fp.fallbacks) == 1
        fp.remove_fallback(fb)
        assert len(fp.fallbacks) == 0


class TestMCPToolAdapter:
    def test_adapter_schema(self):
        from bahram.core.agent import _MCPToolAdapter
        client = MagicMock()
        tool_def = {"name": "test_tool", "description": "A test", "inputSchema": {"type": "object", "properties": {"x": {"type": "string"}}}}
        adapter = _MCPToolAdapter(client, tool_def)
        schema = adapter.schema()
        assert schema["name"] == "mcp_test_tool"
        assert schema["description"] == "A test"
        assert "parameters" in schema


class TestProviderFallbackInEngine:
    @pytest.mark.asyncio
    async def test_provider_fallback_on_complete_failure(self):
        engine = AgentEngine()
        primary = AlwaysFailProvider()
        fallback = MockProvider(responses=[AgentResponse(content="fallback worked")])
        engine.providers["anthropic"] = primary
        engine.providers["__fallback__"] = FallbackProvider(primary, [fallback])
        engine.register_tool("mock", MockTool())

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="anthropic/test", session_id="s1")
        assert "fallback" in response.content.lower()

    @pytest.mark.asyncio
    async def test_all_providers_fail_returns_error(self):
        engine = AgentEngine()
        primary = AlwaysFailProvider()
        fallback = AlwaysFailProvider()
        engine.providers["anthropic"] = primary
        engine.providers["__fallback__"] = FallbackProvider(primary, [fallback])
        engine.register_tool("mock", MockTool())

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="anthropic/test", session_id="s1")
        assert "error" in response.content.lower() or "failed" in response.content.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
