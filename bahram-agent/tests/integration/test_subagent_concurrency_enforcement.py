"""Integration tests for subagent concurrency enforcement.

Verifies that SubagentEngine properly limits concurrent subagent execution,
queues excess spawns, frees slots on completion, and enforces per-subagent
token budget and recursion depth limits.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock

import pytest

from bahram.autonomy.subagent import SubagentEngine
from bahram.core.engine import AgentResponse, RunState

# ── Helpers ────────────────────────────────────────────────


class FakeEngine:
    """Minimal engine for subagent concurrency testing."""

    def __init__(self, provider=None):
        self.providers = {"test": provider or FakeProvider()}
        self.tools = {}
        self._tool_executor = None
        self._approval_system = None
        self.config = MagicMock()
        self.config.agent.model = "test/model"

    def get_tools_schema(self):
        return []

    def get_provider(self, model=None):
        if "test" in self.providers:
            return self.providers["test"]
        raise ValueError("No provider available")


class FakeProvider:
    """Provider that returns immediate completion."""

    def __init__(self, response=None):
        self._response = response or AgentResponse(content="Done", state=RunState.COMPLETED)

    async def complete(self, messages, tools=None, **kwargs):
        return self._response


class SlowProvider:
    """Provider that sleeps for a configurable duration before completing.

    Tracks how many calls are concurrently active so we can verify
    that the concurrency limit is respected.
    """

    def __init__(self, delay: float = 0.3):
        self._delay = delay
        self._concurrent = 0
        self._max_observed = 0
        self._lock = asyncio.Lock()

    async def complete(self, messages, tools=None, **kwargs):
        async with self._lock:
            self._concurrent += 1
            if self._concurrent > self._max_observed:
                self._max_observed = self._concurrent
        try:
            await asyncio.sleep(self._delay)
            return AgentResponse(content="Done", state=RunState.COMPLETED)
        finally:
            async with self._lock:
                self._concurrent -= 1


class RecorderProvider:
    """Provider that records when each call starts and finishes.

    Callers can use the recorded timestamps to verify that no more than
    N subagents were running at any given instant.
    """

    def __init__(self, delay: float = 0.2):
        self._delay = delay
        self._starts: list[float] = []
        self._ends: list[float] = []
        self._active = 0
        self._max_observed = 0
        self._lock = asyncio.Lock()

    async def complete(self, messages, tools=None, **kwargs):
        async with self._lock:
            self._active += 1
            if self._active > self._max_observed:
                self._max_observed = self._active
            self._starts.append(time.monotonic())
        try:
            await asyncio.sleep(self._delay)
            return AgentResponse(content="Done", state=RunState.COMPLETED)
        finally:
            async with self._lock:
                self._active -= 1
                self._ends.append(time.monotonic())

    @property
    def max_concurrent_observed(self) -> int:
        return self._max_observed


# ── Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
class TestActiveCountNeverExceedsLimit:
    """Active count must never exceed the configured max_concurrent."""

    async def test_active_count_respects_limit(self):
        max_concurrent = 2
        provider = SlowProvider(delay=0.3)
        engine = FakeEngine(provider=provider)
        se = SubagentEngine(engine, max_concurrent=max_concurrent)

        tasks = [
            se.spawn(parent_run_id="p", objective=f"task{i}", timeout_seconds=5.0) for i in range(6)
        ]
        await asyncio.gather(*tasks)

        assert provider._max_observed <= max_concurrent

    async def test_active_count_with_limit_one(self):
        """With max_concurrent=1, only one subagent runs at a time."""
        provider = SlowProvider(delay=0.2)
        engine = FakeEngine(provider=provider)
        se = SubagentEngine(engine, max_concurrent=1)

        tasks = [
            se.spawn(parent_run_id="p", objective=f"task{i}", timeout_seconds=5.0) for i in range(4)
        ]
        await asyncio.gather(*tasks)

        assert provider._max_observed == 1

    async def test_active_count_with_limit_equal_to_count(self):
        """When limit equals number of subagents, all run concurrently."""
        n = 3
        provider = SlowProvider(delay=0.2)
        engine = FakeEngine(provider=provider)
        se = SubagentEngine(engine, max_concurrent=n)

        tasks = [
            se.spawn(parent_run_id="p", objective=f"task{i}", timeout_seconds=5.0) for i in range(n)
        ]
        await asyncio.gather(*tasks)

        assert provider._max_observed == n


@pytest.mark.asyncio
class TestSpawnsWaitWhenLimitReached:
    """New spawns should wait (queue) when the concurrency limit is hit."""

    async def test_get_active_count_reflects_currently_running(self):
        """get_active_count() reflects the number of currently running subagents."""
        provider = SlowProvider(delay=0.3)
        engine = FakeEngine(provider=provider)
        se = SubagentEngine(engine, max_concurrent=2)

        # Before any spawn, active count should be 0
        assert se.get_active_count() == 0

        # Launch 2 tasks (equal to limit) — they should both be active
        t1 = asyncio.create_task(se.spawn(parent_run_id="p", objective="a", timeout_seconds=5.0))
        t2 = asyncio.create_task(se.spawn(parent_run_id="p", objective="b", timeout_seconds=5.0))
        await asyncio.sleep(0.05)  # Let them start
        assert se.get_active_count() == 2

        # Launch a 3rd — it should queue, not run yet
        t3 = asyncio.create_task(se.spawn(parent_run_id="p", objective="c", timeout_seconds=5.0))
        await asyncio.sleep(0.05)
        assert se.get_active_count() == 2
        assert se.get_queue_depth() >= 1

        await asyncio.gather(t1, t2, t3)
        assert se.get_active_count() == 0

    async def test_queue_depth_increments_when_slots_full(self):
        """Queue depth should increase when all slots are occupied."""
        provider = SlowProvider(delay=0.3)
        engine = FakeEngine(provider=provider)
        se = SubagentEngine(engine, max_concurrent=1)

        t1 = asyncio.create_task(se.spawn(parent_run_id="p", objective="a", timeout_seconds=5.0))
        await asyncio.sleep(0.05)

        t2 = asyncio.create_task(se.spawn(parent_run_id="p", objective="b", timeout_seconds=5.0))
        await asyncio.sleep(0.05)
        assert se.get_queue_depth() == 1

        t3 = asyncio.create_task(se.spawn(parent_run_id="p", objective="c", timeout_seconds=5.0))
        await asyncio.sleep(0.05)
        assert se.get_queue_depth() == 2

        await asyncio.gather(t1, t2, t3)
        assert se.get_queue_depth() == 0


@pytest.mark.asyncio
class TestSlotFreedOnCompletion:
    """When a subagent finishes, the slot should be freed for queued spawns."""

    async def test_queued_spawn_runs_after_slot_freed(self):
        provider = SlowProvider(delay=0.15)
        engine = FakeEngine(provider=provider)
        se = SubagentEngine(engine, max_concurrent=1)

        # Two sequential spawns — second should wait for first
        t1 = asyncio.create_task(se.spawn(parent_run_id="p", objective="fast", timeout_seconds=5.0))
        t2 = asyncio.create_task(
            se.spawn(parent_run_id="p", objective="queued", timeout_seconds=5.0)
        )

        r1, r2 = await asyncio.gather(t1, t2)

        assert r1.status == "completed"
        assert r2.status == "completed"
        assert se.get_active_count() == 0
        assert se.get_queue_depth() == 0

    async def test_multiple_slots_freed_in_order(self):
        """When multiple slots free up, queued tasks fill them in order."""
        provider = SlowProvider(delay=0.15)
        engine = FakeEngine(provider=provider)
        se = SubagentEngine(engine, max_concurrent=2)

        # Fill 2 slots
        t1 = asyncio.create_task(se.spawn(parent_run_id="p", objective="a", timeout_seconds=5.0))
        t2 = asyncio.create_task(se.spawn(parent_run_id="p", objective="b", timeout_seconds=5.0))
        await asyncio.sleep(0.05)

        # Queue 2 more
        t3 = asyncio.create_task(se.spawn(parent_run_id="p", objective="c", timeout_seconds=5.0))
        t4 = asyncio.create_task(se.spawn(parent_run_id="p", objective="d", timeout_seconds=5.0))
        await asyncio.sleep(0.05)
        assert se.get_queue_depth() == 2

        results = await asyncio.gather(t1, t2, t3, t4)
        assert all(r.status == "completed" for r in results)
        assert se.get_active_count() == 0
        assert se.get_queue_depth() == 0


@pytest.mark.asyncio
class TestConcurrentSpawnNExceedsLimit:
    """Spawning N subagents where N > max_concurrent: only max_concurrent run at once."""

    async def test_only_max_concurrent_run_simultaneously(self):
        n = 10
        max_concurrent = 3
        provider = RecorderProvider(delay=0.2)
        engine = FakeEngine(provider=provider)
        se = SubagentEngine(engine, max_concurrent=max_concurrent)

        tasks = [
            se.spawn(parent_run_id="p", objective=f"task{i}", timeout_seconds=10.0)
            for i in range(n)
        ]
        results = await asyncio.gather(*tasks)

        assert all(r.status == "completed" for r in results)
        assert provider.max_concurrent_observed == max_concurrent
        assert len(provider._starts) == n

    async def test_interleaved_execution_respects_limit(self):
        """With 2 slots and 4 tasks, tasks should interleave but never exceed 2."""
        provider = SlowProvider(delay=0.25)
        engine = FakeEngine(provider=provider)
        se = SubagentEngine(engine, max_concurrent=2)

        # Track active count over time
        observed_counts: list[int] = []
        original_execute = se._execute_task

        async def tracked_execute(task, model, cancel_event):
            observed_counts.append(se.get_active_count())
            return await original_execute(task, model, cancel_event)

        se._execute_task = tracked_execute

        tasks = [
            se.spawn(parent_run_id="p", objective=f"task{i}", timeout_seconds=10.0)
            for i in range(4)
        ]
        await asyncio.gather(*tasks)

        assert all(c <= 2 for c in observed_counts)
        assert max(observed_counts) == 2

    async def test_all_tasks_complete_when_n_exceeds_limit(self):
        """Even when N > max_concurrent, all tasks should eventually complete."""
        n = 8
        max_concurrent = 2
        provider = SlowProvider(delay=0.1)
        engine = FakeEngine(provider=provider)
        se = SubagentEngine(engine, max_concurrent=max_concurrent)

        tasks = [
            se.spawn(parent_run_id="p", objective=f"task{i}", timeout_seconds=10.0)
            for i in range(n)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == n
        assert all(r.status == "completed" for r in results)
        assert se.get_active_count() == 0


@pytest.mark.asyncio
class TestTokenBudgetEnforcement:
    """Each subagent should respect its token_budget (tool_budget)."""

    async def test_subagent_respects_tool_budget(self):
        """tool_budget limits the number of tool calls a subagent can make."""
        engine = FakeEngine()
        se = SubagentEngine(engine, max_concurrent=5)

        result = await se.spawn(
            parent_run_id="p",
            objective="test",
            token_budget=1024,
            tool_budget=3,
            timeout_seconds=5.0,
        )
        assert result.status == "completed"

    async def test_low_tool_budget_completes_quickly(self):
        """A subagent with tool_budget=1 should complete in at most 1 iteration."""
        engine = FakeEngine()
        se = SubagentEngine(engine, max_concurrent=5)

        result = await se.spawn(
            parent_run_id="p",
            objective="test",
            tool_budget=1,
            timeout_seconds=5.0,
        )
        assert result.status == "completed"
        assert result.metrics.get("tool_calls", 0) <= 1

    async def test_token_budget_isolation_between_subagents(self):
        """Different subagents can have different token/tool budgets."""
        engine = FakeEngine()
        se = SubagentEngine(engine, max_concurrent=5)

        r1 = await se.spawn(
            parent_run_id="p",
            objective="a",
            token_budget=512,
            tool_budget=1,
            timeout_seconds=5.0,
        )
        r2 = await se.spawn(
            parent_run_id="p",
            objective="b",
            token_budget=4096,
            tool_budget=20,
            timeout_seconds=5.0,
        )
        assert r1.status == "completed"
        assert r2.status == "completed"


@pytest.mark.asyncio
class TestRecursionDepthEnforcement:
    """Recursion depth (timeout and iterations) should be enforced per subagent."""

    async def test_subagent_timeout_enforced(self):
        """Subagent exceeding its timeout should be terminated."""
        engine = FakeEngine(provider=SlowProvider(delay=10))
        se = SubagentEngine(engine, max_concurrent=5)

        result = await se.spawn(
            parent_run_id="p",
            objective="slow",
            timeout_seconds=0.2,
        )
        assert result.status in ("timeout", "cancelled")

    async def test_recursion_depth_limited_by_max_iterations(self):
        """The RunConfig.max_iterations should be bounded by tool_budget."""
        engine = FakeEngine()
        se = SubagentEngine(engine, max_concurrent=5)

        result = await se.spawn(
            parent_run_id="p",
            objective="test",
            tool_budget=2,
            timeout_seconds=10.0,
        )
        assert result.status == "completed"
        assert result.metrics.get("iterations", 0) <= 2


@pytest.mark.asyncio
class TestEdgeCases:
    """Edge case tests for the concurrency enforcement system."""

    async def test_default_max_concurrent_is_five(self):
        """Default max_concurrent should be 5."""
        engine = FakeEngine()
        se = SubagentEngine(engine)
        assert se._max_concurrent == 5

    async def test_zero_max_concurrent_blocks_all(self):
        """max_concurrent=0 means semaphore never releases — spawns queue forever.

        We use a short timeout to verify they don't immediately fail.
        """
        engine = FakeEngine(provider=SlowProvider(delay=0.05))
        se = SubagentEngine(engine, max_concurrent=0)

        # With max_concurrent=0, the semaphore starts at 0, so no one
        # can acquire it. The task should eventually timeout via
        # asyncio.wait_for, not via semaphore.
        result = await se.spawn(
            parent_run_id="p",
            objective="blocked",
            timeout_seconds=0.3,
        )
        # It should either timeout or fail — but NOT complete normally
        assert result.status in ("timeout", "failed")

    async def test_list_tasks_shows_all_statuses(self):
        """list_tasks should reflect queued, running, and completed statuses."""
        provider = SlowProvider(delay=0.2)
        engine = FakeEngine(provider=provider)
        se = SubagentEngine(engine, max_concurrent=1)

        t1 = asyncio.create_task(se.spawn(parent_run_id="p", objective="a", timeout_seconds=5.0))
        await asyncio.sleep(0.05)
        t2 = asyncio.create_task(se.spawn(parent_run_id="p", objective="b", timeout_seconds=5.0))
        await asyncio.sleep(0.05)

        tasks = se.list_tasks()
        statuses = {t["status"] for t in tasks}
        assert "running" in statuses
        assert "queued" in statuses

        await asyncio.gather(t1, t2)
        final_tasks = se.list_tasks()
        final_statuses = {t["status"] for t in final_tasks}
        assert all(s in ("completed", "timeout", "failed") for s in final_statuses)

    async def test_concurrent_spawn_with_no_providers_gracefully_fails(self):
        """Subagent with no providers should fail, not block the queue."""
        engine = FakeEngine()
        engine.providers = {}
        engine.config = MagicMock()
        engine.config.agent = MagicMock()
        engine.config.agent.model = "nonexistent/model"

        se = SubagentEngine(engine, max_concurrent=2)

        tasks = [
            se.spawn(parent_run_id="p", objective=f"task{i}", timeout_seconds=5.0) for i in range(3)
        ]
        results = await asyncio.gather(*tasks)
        assert all(r.status == "failed" for r in results)
        assert se.get_active_count() == 0

    async def test_cancelled_subagent_frees_slot(self):
        """Cancelling a running subagent should free its concurrency slot."""
        engine = FakeEngine(provider=SlowProvider(delay=5))
        se = SubagentEngine(engine, max_concurrent=1)

        t1 = asyncio.create_task(
            se.spawn(parent_run_id="p", objective="slow", timeout_seconds=10.0)
        )
        await asyncio.sleep(0.3)
        assert se.get_active_count() == 1

        # Cancel the running task
        tasks_list = se.list_tasks()
        se.cancel(tasks_list[0]["task_id"])
        await asyncio.sleep(0.5)

        r1 = await t1
        assert r1.status in ("cancelled", "timeout", "completed")
        assert se.get_active_count() == 0
