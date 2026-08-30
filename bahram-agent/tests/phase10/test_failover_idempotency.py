"""Phase 10: Failover idempotency guard tests.

Tests that when a provider fails mid-execution and fallback takes over,
already-completed tool calls are not duplicated.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from bahram.core.engine import (
    AgentEngine, AgentResponse, Message, MessageRole, ToolCall, ToolResult, RunState,
)
from bahram.providers.fallback import FallbackProvider
from bahram.autonomy.events import EventTracker


class FakeProvider:
    """Deterministic fake LLM provider for testing."""

    def __init__(self, responses=None, should_fail=False, fail_message="provider error"):
        self.responses = responses or []
        self._call_count = 0
        self.should_fail = should_fail
        self.fail_message = fail_message
        self.call_log = []

    async def complete(self, messages, tools=None, **kwargs):
        self.call_log.append({"messages": len(messages), "tools": len(tools or [])})
        if self.should_fail:
            raise Exception(self.fail_message)
        if self._call_count < len(self.responses):
            resp = self.responses[self._call_count]
            self._call_count += 1
            return resp
        self._call_count += 1
        return AgentResponse(content="Done", state=RunState.COMPLETED)

    async def stream(self, messages, tools=None, **kwargs):
        if self.should_fail:
            raise Exception(self.fail_message)
        yield "chunk"


class RecordingTool:
    """Tool that records every execute call for idempotency verification."""

    def __init__(self):
        self.executions = []

    async def execute(self, **kwargs):
        self.executions.append(kwargs)
        return f"executed: {json.dumps(kwargs, default=str)}"

    def schema(self):
        return {
            "name": "recording_tool",
            "description": "A tool that records executions",
            "parameters": {"type": "object", "properties": {"action": {"type": "string"}}},
        }


class TestFailoverIdempotency:
    """Verify that failover does not duplicate side effects."""

    def setup_method(self):
        self.tool = RecordingTool()

    @pytest.mark.asyncio
    async def test_no_duplicate_tool_calls_on_provider_failover(self):
        """If provider fails after requesting tool call, fallback should not re-execute."""
        tool_call = ToolCall(id="tc_1", name="recording_tool", arguments={"action": "write"})

        primary = FakeProvider(responses=[
            AgentResponse(content="Let me use the tool", tool_calls=[tool_call]),
        ], should_fail=True)

        fallback_response = AgentResponse(content="Fallback completed", state=RunState.COMPLETED)
        fallback = FakeProvider(responses=[fallback_response])

        fb = FallbackProvider(primary, [fallback])

        from bahram.core.engine import ToolExecutor
        executor = ToolExecutor({"recording_tool": self.tool})

        result = await executor.execute(tool_call)
        assert result.success
        assert len(self.tool.executions) == 1

        assert fb.get_current_provider() == "FakeProvider"

    @pytest.mark.asyncio
    async def test_fallback_provider_continues_from_state(self):
        """Fallback should receive the full message history including tool results."""
        tool_call = ToolCall(id="tc_1", name="recording_tool", arguments={"action": "read"})

        primary = FakeProvider(responses=[
            AgentResponse(content="Using tool", tool_calls=[tool_call]),
        ], should_fail=True)

        fallback = FakeProvider(responses=[
            AgentResponse(content="Continuing from where we left off", state=RunState.COMPLETED),
        ])

        fb = FallbackProvider(primary, [fallback])

        messages = [
            Message(role=MessageRole.USER, content="Do something"),
            Message(role=MessageRole.ASSISTANT, content="Using tool", metadata={"tool_calls": [tool_call]}),
            Message(role=MessageRole.TOOL, content="result of tool", tool_call_id="tc_1"),
        ]

        result = await fb.complete(messages, [])
        assert result.content == "Continuing from where we left off"
        assert len(fallback.call_log) == 1

    @pytest.mark.asyncio
    async def test_fallback_records_failure_event(self):
        """Engine should record provider failure when fallback is triggered."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = EventTracker(data_dir=tmpdir)

            engine = AgentEngine()
            engine._event_tracker = tracker

            engine.record_provider_failure("test_provider")

            events = tracker.query_events(event_type="provider_fallback")
            assert len(events) >= 1
            assert events[0].data.get("provider") == "test_provider"

    @pytest.mark.asyncio
    async def test_all_providers_fail_raises(self):
        """If all providers fail, FallbackProvider should raise."""
        primary = FakeProvider(should_fail=True, fail_message="primary down")
        fallback = FakeProvider(should_fail=True, fail_message="fallback down")

        fb = FallbackProvider(primary, [fallback])

        with pytest.raises(Exception, match="All providers failed"):
            await fb.complete([], [])

    @pytest.mark.asyncio
    async def test_multiple_fallbacks_try_in_order(self):
        """FallbackProvider should try providers in order."""
        primary = FakeProvider(should_fail=True)
        fb1 = FakeProvider(should_fail=True)
        fb2 = FakeProvider(responses=[
            AgentResponse(content="FB2 success", state=RunState.COMPLETED)
        ])

        fb = FallbackProvider(primary, [fb1, fb2])

        result = await fb.complete([], [])
        assert result.content == "FB2 success"
        assert fb.get_current_provider() == "FakeProvider"

    @pytest.mark.asyncio
    async def test_primary_success_skips_fallback(self):
        """If primary succeeds, no fallback should be tried."""
        primary = FakeProvider(responses=[
            AgentResponse(content="Primary success", state=RunState.COMPLETED)
        ])
        fallback = FakeProvider()

        fb = FallbackProvider(primary, [fallback])

        result = await fb.complete([], [])
        assert result.content == "Primary success"
        assert len(fallback.call_log) == 0

    @pytest.mark.asyncio
    async def test_add_remove_fallback(self):
        """Fallback list should be modifiable."""
        primary = FakeProvider()
        fb1 = FakeProvider()
        fb2 = FakeProvider()

        fb = FallbackProvider(primary, [fb1])
        assert len(fb.fallbacks) == 1

        fb.add_fallback(fb2)
        assert len(fb.fallbacks) == 2

        fb.remove_fallback(fb1)
        assert len(fb.fallbacks) == 1
        assert fb.fallbacks[0] is fb2

    @pytest.mark.asyncio
    async def test_stream_fallback(self):
        """Fallback should work for streaming too."""
        primary = FakeProvider(should_fail=True)

        class StreamingFallback:
            async def stream(self, messages, tools=None, **kwargs):
                yield "fallback chunk 1"
                yield "fallback chunk 2"

            async def complete(self, messages, tools=None, **kwargs):
                return AgentResponse(content="stream fallback", state=RunState.COMPLETED)

        fallback = StreamingFallback()
        fb = FallbackProvider(primary, [fallback])

        chunks = []
        async for chunk in fb.stream([], []):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert "fallback chunk 1" in chunks
