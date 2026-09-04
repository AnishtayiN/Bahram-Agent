from __future__ import annotations

import asyncio
import os
import tempfile
import time
import uuid

import pytest

from bahram.autonomy.budget import BudgetConfig, BudgetManager
from bahram.autonomy.subagent import SubagentEngine, SubagentTask
from bahram.core.engine import (
    AgentEngine,
    AgentResponse,
    Message,
    MessageRole,
    RunConfig,
    ToolCall,
    ToolExecutor,
    ToolResult,
)
from bahram.core.smart_context import SmartContextManager
from bahram.platforms.circuit_breaker import CircuitBreaker

# ---------------------------------------------------------------------------
# Helpers – real components, not mocks of the system under test
# ---------------------------------------------------------------------------

class AlwaysFailProvider:
    """LLM provider that always raises."""

    async def complete(self, messages, tools=None, **kwargs):
        raise Exception("Provider permanently failed")

    async def stream(self, messages, tools=None, **kwargs):
        raise Exception("Provider permanently failed")


class FlakyProvider:
    """Fails the first N calls, then succeeds."""

    def __init__(self, fail_count: int = 1):
        self._fail_count = fail_count
        self._calls = 0

    async def complete(self, messages, tools=None, **kwargs):
        self._calls += 1
        if self._calls <= self._fail_count:
            raise Exception(f"Transient failure #{self._calls}")
        return AgentResponse(content="recovered")

    async def stream(self, messages, tools=None, **kwargs):
        resp = await self.complete(messages, tools, **kwargs)
        yield resp.content


class WorkingProvider:
    """Returns a plain text response (no tool calls)."""

    async def complete(self, messages, tools=None, **kwargs):
        return AgentResponse(content="all good")

    async def stream(self, messages, tools=None, **kwargs):
        yield "all good"


class RaisingTool:
    """Tool whose execute() always raises."""

    def schema(self):
        return {
            "name": "raising_tool",
            "description": "Always raises",
            "parameters": {"type": "object", "properties": {}},
        }

    async def execute(self, **kwargs):
        raise RuntimeError("Tool internal crash")


class SlowTool:
    """Tool that sleeps longer than any reasonable timeout."""

    def schema(self):
        return {
            "name": "slow_tool",
            "description": "Sleeps forever",
            "parameters": {"type": "object", "properties": {}},
        }

    async def execute(self, **kwargs):
        await asyncio.sleep(60)
        return "should not reach"


class FastTool:
    """Tool that completes quickly."""

    def schema(self):
        return {
            "name": "fast_tool",
            "description": "Fast",
            "parameters": {"type": "object", "properties": {}},
        }

    async def execute(self, **kwargs):
        return "done"


# ---------------------------------------------------------------------------
# 1. Provider failure → engine should fallback or fail gracefully
# ---------------------------------------------------------------------------

class TestProviderFailure:
    @pytest.mark.asyncio
    async def test_single_provider_failure_no_fallback(self):
        engine = AgentEngine()
        engine.providers["anthropic"] = AlwaysFailProvider()
        engine.register_tool("fast", FastTool())

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="anthropic/claude-sonnet-4-20250514")

        assert response.state.value in ("failed", "completed")
        assert response.state.value == "failed"

    @pytest.mark.asyncio
    async def test_provider_failure_with_fallback_succeeds(self):
        engine = AgentEngine()
        engine.providers["anthropic"] = AlwaysFailProvider()
        engine.providers["__fallback__"] = WorkingProvider()
        engine.register_tool("fast", FastTool())

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="anthropic/claude-sonnet-4-20250514")

        assert response.content == "all good"


# ---------------------------------------------------------------------------
# 2. Tool failure → engine should continue with error in context
# ---------------------------------------------------------------------------

class TestToolFailure:
    @pytest.mark.asyncio
    async def test_tool_error_appears_in_context(self):
        engine = AgentEngine()
        call_count = 0

        class ToolFailThenSucceedProvider:
            async def complete(self, messages, tools=None, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return AgentResponse(
                        content="",
                        tool_calls=[ToolCall(id="tc1", name="raising_tool", arguments={})],
                    )
                return AgentResponse(content="got error, moving on")
            async def stream(self, messages, tools=None, **kwargs):
                yield ""

        engine.providers["test"] = ToolFailThenSucceedProvider()
        engine.register_tool("raising_tool", RaisingTool())

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="test/model")

        assert response.content == "got error, moving on"
        assert call_count == 2


# ---------------------------------------------------------------------------
# 3. Budget exhaustion → engine should stop
# ---------------------------------------------------------------------------

class TestBudgetExhaustion:
    @pytest.mark.asyncio
    async def test_zero_model_calls_budget(self):
        engine = AgentEngine()
        bm = BudgetManager(BudgetConfig(max_model_calls=0))
        engine.set_budget_manager(bm)
        engine.providers["test"] = WorkingProvider()
        engine.register_tool("fast", FastTool())

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="test/model")

        assert "Budget limit reached" in response.content

    @pytest.mark.asyncio
    async def test_zero_tool_calls_budget(self):
        engine = AgentEngine()
        bm = BudgetManager(BudgetConfig(max_tool_calls=0))
        engine.set_budget_manager(bm)
        engine.providers["test"] = WorkingProvider()
        engine.register_tool("fast", FastTool())

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="test/model")

        assert "Budget limit reached" in response.content

    @pytest.mark.asyncio
    async def test_budget_enforcement_stops_loop(self):
        engine = AgentEngine()
        bm = BudgetManager(BudgetConfig(max_model_calls=0))
        engine.set_budget_manager(bm)

        class TokenHogProvider:
            async def complete(self, messages, tools=None, **kwargs):
                return AgentResponse(content="x" * 400)
            async def stream(self, messages, tools=None, **kwargs):
                yield ""

        engine.providers["test"] = TokenHogProvider()
        engine.register_tool("fast", FastTool())

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="test/model")

        assert "Budget" in response.content or "budget" in response.content.lower()


# ---------------------------------------------------------------------------
# 4. Circuit breaker: repeated failures → circuit opens → fallback used
# ---------------------------------------------------------------------------

class TestCircuitBreakerChaos:
    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold_failures(self):
        cb = CircuitBreaker()
        for _ in range(5):
            cb.record_failure("primary")
        can_exec, reason = cb.can_execute("primary")
        assert not can_exec
        assert "open" in reason

    @pytest.mark.asyncio
    async def test_engine_uses_fallback_when_circuit_open(self):
        engine = AgentEngine()
        engine.providers["anthropic"] = AlwaysFailProvider()
        engine.providers["__fallback__"] = WorkingProvider()
        engine.register_tool("fast", FastTool())

        cb = engine._circuit_breaker
        for _ in range(5):
            cb.record_failure("anthropic")

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="anthropic/claude-sonnet-4-20250514")
        assert response.content == "all good"

    @pytest.mark.asyncio
    async def test_half_open_allows_probe(self):
        cb = CircuitBreaker()
        for _ in range(5):
            cb.record_failure("platform")
        circuit = cb.get_circuit("platform")
        circuit.last_failure = time.time() - 400
        can_exec, _ = cb.can_execute("platform")
        assert can_exec
        assert circuit.state == "half-open"

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(self):
        cb = CircuitBreaker()
        cb.get_circuit("platform").state = "half-open"
        cb.record_success("platform")
        assert cb.get_circuit("platform").state == "closed"
        assert cb.get_circuit("platform").failures == 0


# ---------------------------------------------------------------------------
# 5. Subagent timeout → should return timeout status
# ---------------------------------------------------------------------------

class TestSubagentTimeout:
    @pytest.mark.asyncio
    async def test_slow_provider_times_out(self):
        engine = AgentEngine()

        class SlowProvider:
            async def complete(self, messages, tools=None, **kwargs):
                await asyncio.sleep(10)
                return AgentResponse(content="too slow")
            async def stream(self, messages, tools=None, **kwargs):
                yield ""

        engine.providers["slow"] = SlowProvider()
        engine.register_tool("fast", FastTool())

        subengine = SubagentEngine(engine)
        result = await subengine.spawn(
            parent_run_id="run_1",
            objective="do something",
            model="slow/model",
            timeout_seconds=0.5,
        )
        assert result.status in ("timeout", "cancelled")

    @pytest.mark.asyncio
    async def test_subagent_completion_within_timeout(self):
        engine = AgentEngine()
        engine.providers["fast"] = WorkingProvider()
        engine.register_tool("fast", FastTool())

        subengine = SubagentEngine(engine)
        result = await subengine.spawn(
            parent_run_id="run_1",
            objective="quick task",
            model="fast/model",
            timeout_seconds=10,
        )
        assert result.status == "completed"


# ---------------------------------------------------------------------------
# 6. DB write failure → should handle gracefully
# ---------------------------------------------------------------------------

class TestDBWriteFailure:
    def test_job_engine_readonly_dir(self):
        from bahram.autonomy.jobs import JobEngine
        with tempfile.TemporaryDirectory() as td:
            readonly = os.path.join(td, "readonly_db")
            os.makedirs(readonly)
            os.chmod(readonly, 0o444)
            try:
                engine = JobEngine(data_dir=readonly)
                try:
                    engine._get_conn()
                except (OSError, PermissionError):
                    pass
            finally:
                os.chmod(readonly, 0o755)

    def test_semantic_memory_readonly_dir(self):
        from bahram.memory.semantic import SemanticMemory
        with tempfile.TemporaryDirectory() as td:
            readonly = os.path.join(td, "readonly_mem")
            os.makedirs(readonly)
            os.chmod(readonly, 0o444)
            try:
                memory = SemanticMemory(data_dir=readonly)
                try:
                    memory.add(content="test", source="test")
                except (OSError, PermissionError):
                    pass
                finally:
                    memory.close()
            finally:
                os.chmod(readonly, 0o755)


# ---------------------------------------------------------------------------
# 7. Context overflow → should compress and survive
# ---------------------------------------------------------------------------

class TestContextOverflow:
    def test_tiny_max_tokens_survives(self):
        scm = SmartContextManager(max_tokens=20)
        scm.set_system_prompt("You are helpful.")
        scm.add_context("Important info here", priority=10)
        scm.add_history("user", "hello world this is a long message")
        scm.add_history("assistant", "response that is also somewhat long")

        messages = scm.build_messages()
        assert len(messages) >= 1

    def test_optimize_removes_low_priority_when_over(self):
        scm = SmartContextManager(max_tokens=20)
        scm.add_context("x" * 50, priority=1)
        scm.add_context("y" * 50, priority=100)

        removed = scm.optimize()
        assert removed >= 1
        assert len(scm._windows) == 1
        assert scm._windows[0].priority == 100

    def test_build_context_fits_within_limit(self):
        scm = SmartContextManager(max_tokens=50)
        scm.set_system_prompt("sys")
        for i in range(20):
            scm.add_history("user", f"msg {i} " + "x" * 20)
        messages = scm.build_context()
        total_tokens = sum(len(m["content"]) // 4 for m in messages)
        assert total_tokens <= 50


# ---------------------------------------------------------------------------
# 8. Concurrent provider failures → should fail safely
# ---------------------------------------------------------------------------

class TestConcurrentProviderFailures:
    @pytest.mark.asyncio
    async def test_all_providers_fail_safely(self):
        engine = AgentEngine()
        engine.providers["p1"] = AlwaysFailProvider()
        engine.providers["p2"] = AlwaysFailProvider()
        engine.providers["p3"] = AlwaysFailProvider()
        engine.register_tool("fast", FastTool())

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="p1/model")

        assert response.state.value == "failed"
        assert "error" in response.content.lower() or "failed" in response.content.lower()

    @pytest.mark.asyncio
    async def test_concurrent_budget_checks(self):
        engine = AgentEngine()
        bm = BudgetManager(BudgetConfig(max_total_tokens=100, max_model_calls=1))
        engine.set_budget_manager(bm)
        engine.providers["test"] = WorkingProvider()
        engine.register_tool("fast", FastTool())

        messages1 = [Message(role=MessageRole.USER, content="first")]
        resp1 = await engine.run(messages1, model="test/model")
        assert resp1.content == "all good"

        messages2 = [Message(role=MessageRole.USER, content="second")]
        resp2 = await engine.run(messages2, model="test/model")
        assert resp2.content == "all good"


# ---------------------------------------------------------------------------
# 9. Tool timeout → should be killed
# ---------------------------------------------------------------------------

class TestToolTimeout:
    @pytest.mark.asyncio
    async def test_slow_tool_killed_by_timeout(self):
        executor = ToolExecutor({"slow_tool": SlowTool()}, None)
        tc = ToolCall(id="tc_slow", name="slow_tool", arguments={})
        result = await executor.execute(tc, timeout=0.5)

        assert not result.success
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_fast_tool_completes_within_timeout(self):
        executor = ToolExecutor({"fast_tool": FastTool()}, None)
        tc = ToolCall(id="tc_fast", name="fast_tool", arguments={})
        result = await executor.execute(tc, timeout=5.0)

        assert result.success
        assert result.content == "done"


# ---------------------------------------------------------------------------
# 10. Cancellation during tool execution → should stop
# ---------------------------------------------------------------------------

class TestCancellationDuringTool:
    @pytest.mark.asyncio
    async def test_cancel_event_stops_engine(self):
        engine = AgentEngine()

        class CancelProvider:
            def __init__(self):
                self.call_count = 0
            async def complete(self, messages, tools=None, **kwargs):
                self.call_count += 1
                if self.call_count == 1:
                    engine.cancel()
                    return AgentResponse(
                        content="",
                        tool_calls=[ToolCall(id="tc1", name="fast", arguments={})],
                    )
                return AgentResponse(content="should not run")
            async def stream(self, messages, tools=None, **kwargs):
                yield ""

        engine.providers["test"] = CancelProvider()
        engine.register_tool("fast", FastTool())

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="test/model")

        assert response.state.value == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_between_iterations(self):
        engine = AgentEngine()

        class ToolProvider:
            def __init__(self):
                self.call_count = 0
            async def complete(self, messages, tools=None, **kwargs):
                self.call_count += 1
                if self.call_count == 1:
                    engine._cancel_event.set()
                    return AgentResponse(
                        content="",
                        tool_calls=[ToolCall(id="tc1", name="fast_tool", arguments={})],
                    )
                return AgentResponse(content="should not run")
            async def stream(self, messages, tools=None, **kwargs):
                yield ""

        engine.providers["test"] = ToolProvider()
        engine.register_tool("fast_tool", FastTool())

        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="test/model")

        assert response.state.value == "cancelled"

    @pytest.mark.asyncio
    async def test_subagent_cancellation(self):
        engine = AgentEngine()
        engine.providers["test"] = WorkingProvider()
        engine.register_tool("fast", FastTool())

        subengine = SubagentEngine(engine)

        async def spawn_and_cancel():
            task = asyncio.create_task(
                subengine.spawn(
                    parent_run_id="run_cancel",
                    objective="long task",
                    model="test/model",
                    timeout_seconds=30,
                )
            )
            await asyncio.sleep(0.01)
            for task_id in list(subengine._cancel_events.keys()):
                subengine.cancel(task_id)
            return await task

        result = await spawn_and_cancel()
        assert result.status in ("cancelled", "completed")
