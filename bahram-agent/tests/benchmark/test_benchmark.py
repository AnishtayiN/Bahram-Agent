from __future__ import annotations

import asyncio
import tempfile
import time
import pytest
from unittest.mock import AsyncMock, MagicMock

from bahram.core.engine import (
    AgentEngine, AgentResponse, Message, MessageRole,
    RunState, ToolCall, ToolResult, ToolExecutor, Trajectory,
)
from bahram.core.persistence import SessionStore
from bahram.memory.semantic import SemanticMemory


def _mock_provider(responses):
    idx = [0]

    async def complete(messages, tools=None, **kwargs):
        if idx[0] < len(responses):
            r = responses[idx[0]]
            idx[0] += 1
            return r
        return AgentResponse(content="done")

    mock = MagicMock()
    mock.complete = complete
    return mock


class TestBasicConversation:
    @pytest.mark.asyncio
    async def test_simple_greeting(self):
        engine = AgentEngine()
        engine.register_provider("test", _mock_provider([
            AgentResponse(content="Hello! How can I help you?"),
        ]))
        messages = [Message(role=MessageRole.USER, content="Hi")]
        result = await engine.run(messages, model="test/model")
        assert result.state == RunState.COMPLETED
        assert "Hello" in result.content

    @pytest.mark.asyncio
    async def test_multi_turn(self):
        engine = AgentEngine()
        engine.register_provider("test", _mock_provider([
            AgentResponse(content="I can help with that."),
            AgentResponse(content="Done! Here's the summary."),
        ]))
        messages = [
            Message(role=MessageRole.USER, content="Write a function"),
            Message(role=MessageRole.ASSISTANT, content="I can help with that."),
            Message(role=MessageRole.USER, content="Now run it"),
        ]
        result = await engine.run(messages, model="test/model")
        assert result.state == RunState.COMPLETED


class TestToolExecution:
    @pytest.mark.asyncio
    async def test_tool_executor_success(self):
        class MockTool:
            async def execute(self, **kw):
                return "42"
            def schema(self):
                return {"name": "mock", "inputSchema": {"type": "object", "properties": {}}}

        executor = ToolExecutor({"mock": MockTool()})
        tc = ToolCall(id="1", name="mock", arguments={})
        result = await executor.execute(tc)
        assert result.success
        assert result.content == "42"

    @pytest.mark.asyncio
    async def test_tool_executor_timeout(self):
        class SlowTool:
            async def execute(self, **kw):
                await asyncio.sleep(100)
                return "never"
            def schema(self):
                return {"name": "slow", "inputSchema": {"type": "object", "properties": {}}}

        executor = ToolExecutor({"slow": SlowTool()})
        tc = ToolCall(id="1", name="slow", arguments={})
        result = await executor.execute(tc, timeout=0.1)
        assert not result.success
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_tool_executor_unknown_tool(self):
        executor = ToolExecutor({})
        tc = ToolCall(id="1", name="nonexistent", arguments={})
        result = await executor.execute(tc)
        assert not result.success
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_tool_executor_exception_handling(self):
        class BrokenTool:
            async def execute(self, **kw):
                raise ValueError("disk full")
            def schema(self):
                return {"name": "broken", "inputSchema": {"type": "object", "properties": {}}}

        executor = ToolExecutor({"broken": BrokenTool()})
        tc = ToolCall(id="1", name="broken", arguments={})
        result = await executor.execute(tc)
        assert not result.success
        assert "disk full" in result.error


class TestStateTransitions:
    def test_run_state_values(self):
        assert RunState.CREATED.value == "created"
        assert RunState.THINKING.value == "thinking"
        assert RunState.COMPLETED.value == "completed"
        assert RunState.FAILED.value == "failed"
        assert RunState.CANCELLED.value == "cancelled"

    def test_trajectory_to_dict(self):
        t = Trajectory(run_id="r1", session_id="s1", goal="test goal")
        d = t.to_dict()
        assert d["run_id"] == "r1"
        assert d["session_id"] == "s1"
        assert d["status"] == "running"
        assert d["total_tool_calls"] == 0


class TestMemoryIntegration:
    def test_memory_add_and_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mem = SemanticMemory(data_dir=tmpdir)
            mid = mem.add(content="Python is a programming language", source="test")
            assert mid
            results = mem.search("Python")
            assert len(results) > 0
            mem.close()

    def test_memory_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mem = SemanticMemory(data_dir=tmpdir)
            mid = mem.add(content="Test memory", source="test")
            assert mem.delete(mid)
            assert mem.get(mid) is None
            mem.close()

    def test_memory_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mem = SemanticMemory(data_dir=tmpdir)
            mem.add(content="The sky is blue", source="nature")
            mem.add(content="Grass is green", source="nature")
            ctx = mem.get_context("sky")
            assert len(ctx) > 0
            mem.close()


class TestPersistenceIntegration:
    def test_session_crud(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(db_path=f"{tmpdir}/test.db")
            store.create_session("s1", user_id="u1", channel="cli", model="test")
            s = store.get_session("s1")
            assert s is not None
            assert s["user_id"] == "u1"
            store.delete_session("s1")
            assert store.get_session("s1") is None

    def test_message_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(db_path=f"{tmpdir}/test.db")
            store.create_session("s1")
            msg = Message(role=MessageRole.USER, content="Hello world")
            msg_id = store.add_message("s1", msg)
            assert msg_id
            messages = store.get_messages("s1")
            assert len(messages) == 1
            assert messages[0].content == "Hello world"

    def test_trajectory_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(db_path=f"{tmpdir}/test.db")
            store.create_session("s1")
            from bahram.core.engine import TrajectoryStep
            t = Trajectory(run_id="r1", session_id="s1", goal="test")
            t.steps.append(TrajectoryStep(
                step_id="s1", iteration=0, provider="test", model="m",
                tool_calls=[], tool_results=[], content_length=10,
                duration_ms=50.0, timestamp=time.time(),
            ))
            t.status = "completed"
            t.total_tool_calls = 1
            t.total_duration_ms = 100.0
            store.save_trajectory(t, "s1")
            stored = store.get_trajectory("r1")
            assert stored is not None
            assert stored["run"]["status"] == "completed"

    def test_event_logging(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(db_path=f"{tmpdir}/test.db")
            eid = store.log_event("test_event", "test_source", {"key": "value"})
            assert eid
            events = store.get_events("test_event")
            assert len(events) == 1


class TestCancellation:
    def test_engine_cancel(self):
        engine = AgentEngine()
        engine.cancel()
        assert engine._cancel_event.is_set()
        engine.reset_cancel()
        assert not engine._cancel_event.is_set()


class TestRunConfig:
    def test_default_config(self):
        engine = AgentEngine()
        cfg = engine._get_run_config()
        assert cfg.max_iterations == 15
        assert cfg.max_runtime_seconds == 300.0
        assert cfg.max_tool_calls == 50

    def test_custom_config(self):
        class MockConfig:
            agent = type("Agent", (), {"max_iterations": 5, "max_runtime_seconds": 60.0, "max_tool_calls": 10})()
            tools = type("Tools", (), {"bash_timeout": 30})()
        engine = AgentEngine(config=MockConfig())
        cfg = engine._get_run_config()
        assert cfg.max_iterations == 5
        assert cfg.max_runtime_seconds == 60.0
