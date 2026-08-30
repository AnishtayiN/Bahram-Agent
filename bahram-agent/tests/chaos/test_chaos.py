from __future__ import annotations

import asyncio
import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any

from bahram.core.engine import AgentEngine, AgentResponse, Message, MessageRole
from bahram.providers.fallback import FallbackProvider


class AlwaysFailProvider:
    async def complete(self, messages, tools=None, **kwargs):
        raise Exception("Provider permanently failed")

    async def stream(self, messages, tools=None, **kwargs):
        raise Exception("Provider permanently failed")


class MockProvider:
    def __init__(self, responses=None):
        self._responses = list(responses or [])

    async def complete(self, messages, tools=None, **kwargs):
        if self._responses:
            return self._responses.pop(0)
        return AgentResponse(content="done")

    async def stream(self, messages, tools=None, **kwargs):
        resp = await self.complete(messages, tools, **kwargs)
        yield resp.content


class MockTool:
    def schema(self):
        return {"name": "mock", "description": "mock", "parameters": {"type": "object", "properties": {}}}

    async def execute(self, **kwargs):
        return "ok"


class TestCircuitBreakerTransitions:
    def test_closed_to_open(self):
        engine = AgentEngine()
        cb = engine._circuit_breaker
        for _ in range(5):
            engine.record_provider_failure("test")
        assert cb.get_circuit("test").state == "open"

    def test_open_to_half_open(self):
        engine = AgentEngine()
        cb = engine._circuit_breaker
        for _ in range(5):
            engine.record_provider_failure("test")
        circuit = cb.get_circuit("test")
        circuit.last_failure = time.time() - 400
        can_exec, _ = cb.can_execute("test")
        assert can_exec
        assert circuit.state == "half-open"

    def test_half_open_to_closed(self):
        engine = AgentEngine()
        cb = engine._circuit_breaker
        for _ in range(5):
            engine.record_provider_failure("test")
        cb.get_circuit("test").state = "half-open"
        engine.record_provider_success("test")
        assert cb.get_circuit("test").state == "closed"

    def test_half_open_to_open_on_failure(self):
        engine = AgentEngine()
        cb = engine._circuit_breaker
        for _ in range(5):
            engine.record_provider_failure("test")
        cb.get_circuit("test").state = "half-open"
        engine.record_provider_failure("test")
        assert cb.get_circuit("test").state == "open"


class TestBudgetEnforcement:
    @pytest.mark.asyncio
    async def test_budget_stops_execution(self):
        from bahram.autonomy.budget import BudgetManager, BudgetConfig
        engine = AgentEngine()
        bm = BudgetManager(BudgetConfig(max_model_calls=0))
        engine.set_budget_manager(bm)
        engine.providers["test"] = MockProvider(responses=[AgentResponse(content="hi")])
        engine.register_tool("mock", MockTool())

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="test/model")
        assert "Budget limit reached" in response.content

    @pytest.mark.asyncio
    async def test_budget_allows_within_limit(self):
        from bahram.autonomy.budget import BudgetManager, BudgetConfig
        engine = AgentEngine()
        bm = BudgetManager(BudgetConfig(max_model_calls=100))
        engine.set_budget_manager(bm)
        engine.providers["test"] = MockProvider(responses=[AgentResponse(content="ok")])
        engine.register_tool("mock", MockTool())

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="test/model")
        assert response.content == "ok"


class TestProviderFailover:
    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self):
        engine = AgentEngine()
        primary = AlwaysFailProvider()
        fallback = MockProvider(responses=[AgentResponse(content="fallback worked")])
        engine.providers["anthropic"] = primary
        engine.providers["__fallback__"] = FallbackProvider(primary, [fallback])
        engine.register_tool("mock", MockTool())

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="anthropic/test")
        assert "fallback" in response.content.lower()

    @pytest.mark.asyncio
    async def test_all_fail_returns_error(self):
        engine = AgentEngine()
        primary = AlwaysFailProvider()
        fallback = AlwaysFailProvider()
        engine.providers["anthropic"] = primary
        engine.providers["__fallback__"] = FallbackProvider(primary, [fallback])
        engine.register_tool("mock", MockTool())

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="anthropic/test")
        assert "error" in response.content.lower() or "failed" in response.content.lower()


class TestLoopTermination:
    @pytest.mark.asyncio
    async def test_max_iterations_stops(self):
        from bahram.core.engine import RunConfig
        engine = AgentEngine()
        engine._get_run_config = lambda: RunConfig(max_iterations=3, max_tool_calls=100)
        call_count = 0

        class InfiniteToolProvider:
            async def complete(self, messages, tools=None, **kwargs):
                nonlocal call_count
                call_count += 1
                from bahram.core.engine import ToolCall
                return AgentResponse(
                    content="",
                    tool_calls=[ToolCall(id=f"tc_{call_count}", name="mock", arguments={})],
                )

            async def stream(self, messages, tools=None, **kwargs):
                yield ""

        engine.providers["test"] = InfiniteToolProvider()
        engine.register_tool("mock", MockTool())

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="test/model")
        assert call_count <= 3


class TestCancellation:
    @pytest.mark.asyncio
    async def test_cancel_stops_execution(self):
        engine = AgentEngine()
        from bahram.core.engine import ToolCall

        class CancelAfterToolProvider:
            def __init__(self):
                self.call_count = 0
            async def complete(self, messages, tools=None, **kwargs):
                self.call_count += 1
                if self.call_count == 1:
                    return AgentResponse(
                        content="",
                        tool_calls=[ToolCall(id="tc1", name="mock", arguments={})],
                    )
                engine._cancel_event.set()
                return AgentResponse(content="should not reach here")
            async def stream(self, messages, tools=None, **kwargs):
                yield ""

        provider = CancelAfterToolProvider()
        engine.providers["test"] = provider
        engine.register_tool("mock", MockTool())

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="test/model")
        assert provider.call_count <= 2


class TestEventTrackerWiring:
    def test_events_emitted_on_provider_failure(self):
        from bahram.autonomy.events import EventTracker
        engine = AgentEngine()
        et = EventTracker()
        engine.set_event_tracker(et)
        engine.record_provider_failure("test")
        events = et.query_events(event_type="provider_fallback")
        assert len(events) > 0


class TestSmartContextBuildMessages:
    def test_build_messages_returns_engine_compatible(self):
        from bahram.core.smart_context import SmartContextManager
        scm = SmartContextManager(max_tokens=1000)
        scm.set_system_prompt("You are helpful.")
        scm.add_history("user", "hello")
        scm.add_history("assistant", "hi there")
        messages = scm.build_messages()
        assert len(messages) >= 2
        from bahram.core.engine import Message
        for m in messages:
            assert isinstance(m, Message)
