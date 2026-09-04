from __future__ import annotations

import asyncio

import pytest

from bahram.core.engine import (
    AgentResponse,
    Message,
    MessageRole,
    RunState,
    ToolCall,
    ToolExecutor,
)
from bahram.providers.fallback import FallbackProvider


class CounterTool:
    """Tool that increments a counter on every real execution.

    Idempotency is NOT handled here — it is handled by ToolExecutor's
    _result_cache keyed by tool_call_id.  This tool just counts how many
    times its execute() method is actually invoked.
    """

    def __init__(self):
        self.counter = 0
        self.execution_log: list[str] = []

    async def execute(self, **kwargs) -> str:
        self.counter += 1
        result = f"count={self.counter}"
        self.execution_log.append(f"executed:{self.counter}")
        return result

    def schema(self):
        return {
            "name": "counter",
            "description": "Increments a global counter",
            "parameters": {"type": "object", "properties": {}},
        }


class FakeProvider:
    """Deterministic fake LLM provider."""

    def __init__(self, responses=None, should_fail=False, fail_msg="provider error"):
        self.responses = responses or []
        self._call_idx = 0
        self.should_fail = should_fail
        self.fail_msg = fail_msg
        self.call_count = 0

    async def complete(self, messages, tools=None, **kwargs):
        self.call_count += 1
        if self.should_fail:
            raise Exception(self.fail_msg)
        if self._call_idx < len(self.responses):
            resp = self.responses[self._call_idx]
            self._call_idx += 1
            return resp
        return AgentResponse(content="Done", state=RunState.COMPLETED)

    async def stream(self, messages, tools=None, **kwargs):
        if self.should_fail:
            raise Exception(self.fail_msg)
        yield "chunk"


# ---------------------------------------------------------------------------
# 1. CounterTool basics (no caching — proves counting works)
# ---------------------------------------------------------------------------

class TestCounterToolBasics:
    """Verify the CounterTool increments on every call (no built-in cache)."""

    @pytest.mark.asyncio
    async def test_single_execution_increments_counter(self):
        tool = CounterTool()
        result = await tool.execute()
        assert tool.counter == 1
        assert result == "count=1"

    @pytest.mark.asyncio
    async def test_each_execution_increments(self):
        tool = CounterTool()
        await tool.execute()
        await tool.execute()
        assert tool.counter == 2


# ---------------------------------------------------------------------------
# 2. ToolExecutor idempotency via _result_cache
# ---------------------------------------------------------------------------

class TestToolExecutorIdempotency:
    """Prove that ToolExecutor caches ToolResults by tool_call_id,
    preventing duplicate side effects on re-execution."""

    def _executor_for(self, tool: CounterTool) -> ToolExecutor:
        return ToolExecutor({"counter": tool})

    @pytest.mark.asyncio
    async def test_single_execution(self):
        tool = CounterTool()
        executor = self._executor_for(tool)
        tc = ToolCall(id="tc_a", name="counter", arguments={})
        result = await executor.execute(tc)
        assert result.success
        assert tool.counter == 1

    @pytest.mark.asyncio
    async def test_same_tool_call_id_returns_cached_result(self):
        tool = CounterTool()
        executor = self._executor_for(tool)
        tc = ToolCall(id="tc_a", name="counter", arguments={})
        r1 = await executor.execute(tc)
        r2 = await executor.execute(tc)
        assert tool.counter == 1
        assert r1.content == r2.content == "count=1"

    @pytest.mark.asyncio
    async def test_different_tool_call_ids_execute_fresh(self):
        tool = CounterTool()
        executor = self._executor_for(tool)
        tc1 = ToolCall(id="tc_1", name="counter", arguments={})
        tc2 = ToolCall(id="tc_2", name="counter", arguments={})
        r1 = await executor.execute(tc1)
        r2 = await executor.execute(tc2)
        assert tool.counter == 2
        assert r1.content == "count=1"
        assert r2.content == "count=2"

    @pytest.mark.asyncio
    async def test_retry_same_id_returns_cached(self):
        tool = CounterTool()
        executor = self._executor_for(tool)
        tc = ToolCall(id="retry_1", name="counter", arguments={})
        first = await executor.execute(tc)
        for _ in range(5):
            cached = await executor.execute(tc)
        assert tool.counter == 1
        assert cached.content == first.content

    @pytest.mark.asyncio
    async def test_retry_different_id_executes_fresh(self):
        tool = CounterTool()
        executor = self._executor_for(tool)
        tc1 = ToolCall(id="a", name="counter", arguments={})
        tc2 = ToolCall(id="b", name="counter", arguments={})
        await executor.execute(tc1)
        r2 = await executor.execute(tc2)
        assert tool.counter == 2
        assert r2.content == "count=2"

    @pytest.mark.asyncio
    async def test_mixed_ids_interleaved(self):
        tool = CounterTool()
        executor = self._executor_for(tool)
        calls = [
            ToolCall(id="x", name="counter", arguments={}),
            ToolCall(id="y", name="counter", arguments={}),
            ToolCall(id="x", name="counter", arguments={}),
            ToolCall(id="z", name="counter", arguments={}),
            ToolCall(id="y", name="counter", arguments={}),
        ]
        results = [await executor.execute(tc) for tc in calls]
        assert tool.counter == 3
        assert [r.content for r in results] == [
            "count=1", "count=2", "count=1", "count=3", "count=2"
        ]

    @pytest.mark.asyncio
    async def test_cache_is_populated(self):
        tool = CounterTool()
        executor = self._executor_for(tool)
        tc = ToolCall(id="cache_check", name="counter", arguments={})
        await executor.execute(tc)
        assert "cache_check" in executor._result_cache
        assert executor._result_cache["cache_check"].content == "count=1"


# ---------------------------------------------------------------------------
# 3. FallbackProvider does not re-execute completed tool calls
# ---------------------------------------------------------------------------

class TestFallbackProviderIdempotency:
    """Prove that when FallbackProvider takes over, already-completed
    tool calls are not re-executed — the message history carries the results."""

    @pytest.mark.asyncio
    async def test_fallback_receives_tool_results_in_messages(self):
        """Primary executes a tool then fails; fallback gets the tool result
        already in the message history — no re-execution."""
        tool = CounterTool()
        executor = ToolExecutor({"counter": tool})

        tc = ToolCall(id="tc_1", name="counter", arguments={})
        result = await executor.execute(tc)
        assert tool.counter == 1

        messages = [
            Message(role=MessageRole.USER, content="do something"),
            Message(role=MessageRole.ASSISTANT, content="calling tool",
                    metadata={"tool_calls": [tc]}),
            Message(role=MessageRole.TOOL, content=result.content,
                    tool_call_id="tc_1"),
        ]

        primary = FakeProvider(should_fail=True, fail_msg="primary crashed")
        fallback = FakeProvider(responses=[
            AgentResponse(content="fallback done", state=RunState.COMPLETED)
        ])
        fb = FallbackProvider(primary, [fallback])

        resp = await fb.complete(messages, [])
        assert resp.content == "fallback done"
        assert fallback.call_count == 1
        assert tool.counter == 1

    @pytest.mark.asyncio
    async def test_fallback_does_not_duplicate_tool_side_effects(self):
        """Simulate: primary returns tool_call, executor runs it, primary
        then fails on next LLM call. Fallback gets the message with the
        tool result already appended — no second counter increment."""
        tool = CounterTool()
        executor = ToolExecutor({"counter": tool})

        tc = ToolCall(id="failover_tc", name="counter", arguments={})
        exec_result = await executor.execute(tc)
        assert tool.counter == 1

        messages = [
            Message(role=MessageRole.USER, content="run task"),
            Message(role=MessageRole.ASSISTANT, content="using counter",
                    metadata={"tool_calls": [tc]}),
            Message(role=MessageRole.TOOL, content=exec_result.content,
                    tool_call_id="failover_tc"),
        ]

        primary = FakeProvider(should_fail=True)
        fallback = FakeProvider(responses=[
            AgentResponse(content="continued", state=RunState.COMPLETED)
        ])
        fb = FallbackProvider(primary, [fallback])

        resp = await fb.complete(messages, [])
        assert resp.content == "continued"
        assert tool.counter == 1

    @pytest.mark.asyncio
    async def test_full_failover_cycle_preserves_idempotency(self):
        """End-to-end: primary calls tool -> primary fails on next call ->
        fallback completes with message history. Counter only increments once."""
        tool = CounterTool()
        executor = ToolExecutor({"counter": tool})

        tc1 = ToolCall(id="step1", name="counter", arguments={})
        r1 = await executor.execute(tc1)
        assert tool.counter == 1

        tc2 = ToolCall(id="step2", name="counter", arguments={})
        r2 = await executor.execute(tc2)
        assert tool.counter == 2

        messages = [
            Message(role=MessageRole.USER, content="multi-step task"),
            Message(role=MessageRole.ASSISTANT, content="step 1",
                    metadata={"tool_calls": [tc1]}),
            Message(role=MessageRole.TOOL, content=r1.content,
                    tool_call_id="step1"),
            Message(role=MessageRole.ASSISTANT, content="step 2",
                    metadata={"tool_calls": [tc2]}),
            Message(role=MessageRole.TOOL, content=r2.content,
                    tool_call_id="step2"),
        ]

        primary = FakeProvider(should_fail=True, fail_msg="network error")
        fallback = FakeProvider(responses=[
            AgentResponse(content="all done", state=RunState.COMPLETED)
        ])
        fb = FallbackProvider(primary, [fallback])

        resp = await fb.complete(messages, [])
        assert resp.content == "all done"
        assert tool.counter == 2

    @pytest.mark.asyncio
    async def test_failover_same_tool_call_id_twice(self):
        """Simulate a real failover where the same tool_call_id is
        attempted twice — only one side effect should occur."""
        tool = CounterTool()
        executor = ToolExecutor({"counter": tool})

        tc = ToolCall(id="dup_id", name="counter", arguments={})
        r1 = await executor.execute(tc)
        assert tool.counter == 1

        r2 = await executor.execute(tc)
        assert tool.counter == 1
        assert r1.content == r2.content

        messages = [
            Message(role=MessageRole.USER, content="task"),
            Message(role=MessageRole.ASSISTANT, content="exec",
                    metadata={"tool_calls": [tc]}),
            Message(role=MessageRole.TOOL, content=r2.content,
                    tool_call_id="dup_id"),
        ]

        primary = FakeProvider(should_fail=True)
        fallback = FakeProvider(responses=[
            AgentResponse(content="fallback", state=RunState.COMPLETED)
        ])
        fb = FallbackProvider(primary, [fallback])

        resp = await fb.complete(messages, [])
        assert resp.content == "fallback"
        assert tool.counter == 1

    @pytest.mark.asyncio
    async def test_multiple_fallbacks_preserve_idempotency(self):
        """When primary fails and multiple fallbacks are tried, tool
        side effects are not duplicated."""
        tool = CounterTool()
        executor = ToolExecutor({"counter": tool})

        tc = ToolCall(id="multi_fb", name="counter", arguments={})
        r = await executor.execute(tc)
        assert tool.counter == 1

        messages = [
            Message(role=MessageRole.USER, content="task"),
            Message(role=MessageRole.ASSISTANT, content="exec",
                    metadata={"tool_calls": [tc]}),
            Message(role=MessageRole.TOOL, content=r.content,
                    tool_call_id="multi_fb"),
        ]

        primary = FakeProvider(should_fail=True)
        fb1 = FakeProvider(should_fail=True, fail_msg="fb1 down")
        fb2 = FakeProvider(responses=[
            AgentResponse(content="fb2 ok", state=RunState.COMPLETED)
        ])
        fb = FallbackProvider(primary, [fb1, fb2])

        resp = await fb.complete(messages, [])
        assert resp.content == "fb2 ok"
        assert tool.counter == 1


# ---------------------------------------------------------------------------
# 4. Concurrent idempotency
# ---------------------------------------------------------------------------

class TestConcurrentIdempotency:
    """Verify idempotency holds under concurrent execution."""

    @pytest.mark.asyncio
    async def test_concurrent_same_id_only_one_executes(self):
        tool = CounterTool()
        executor = ToolExecutor({"counter": tool})
        tc = ToolCall(id="concurrent_tc", name="counter", arguments={})

        results = await asyncio.gather(
            executor.execute(tc),
            executor.execute(tc),
            executor.execute(tc),
        )

        assert tool.counter == 1
        assert all(r.content == "count=1" for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_different_ids_all_execute(self):
        tool = CounterTool()
        executor = ToolExecutor({"counter": tool})
        calls = [ToolCall(id=f"cid_{i}", name="counter", arguments={}) for i in range(10)]

        results = await asyncio.gather(*(executor.execute(tc) for tc in calls))

        assert tool.counter == 10
        unique_contents = set(r.content for r in results)
        assert len(unique_contents) == 10
        assert all(r.content.startswith("count=") for r in results)
