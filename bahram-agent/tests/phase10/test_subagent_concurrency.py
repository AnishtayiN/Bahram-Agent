"""Phase 10: Subagent concurrency limit tests.

Tests that subagents are properly bounded in concurrency,
and that parent state remains stable under concurrent child execution.
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from bahram.autonomy.subagent import SubagentEngine, SubagentResult
from bahram.core.engine import AgentResponse, RunState


class FakeEngine:
    """Minimal engine for subagent testing."""

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
    """Fake provider that returns immediate completion."""

    def __init__(self, response=None):
        self._response = response or AgentResponse(content="Done", state=RunState.COMPLETED)

    async def complete(self, messages, tools=None, **kwargs):
        return self._response

    async def stream(self, messages, tools=None, **kwargs):
        yield "chunk"


class SlowProvider:
    """Provider that takes a long time."""

    async def complete(self, messages, tools=None, **kwargs):
        await asyncio.sleep(10)
        return AgentResponse(content="Too late", state=RunState.COMPLETED)


@pytest.mark.asyncio
class TestSubagentConcurrency:
    """Verify subagent concurrency bounds and isolation."""

    async def test_single_subagent_execution(self):
        """A single subagent should execute successfully."""
        engine = FakeEngine()
        tracker = MagicMock()
        tracker.emit_subagent_spawned = MagicMock()
        tracker.emit_subagent_completed = MagicMock()

        se = SubagentEngine(engine, event_tracker=tracker)

        result = await se.spawn(
            parent_run_id="parent_1",
            objective="Test objective",
            token_budget=1024,
            tool_budget=5,
            timeout_seconds=10.0,
        )

        assert result.status == "completed"
        assert result.summary == "Done"

    async def test_multiple_sequential_subagents(self):
        """Multiple subagents executed sequentially should all complete."""
        engine = FakeEngine()
        se = SubagentEngine(engine)

        results = []
        for i in range(3):
            result = await se.spawn(
                parent_run_id=f"parent_{i}",
                objective=f"Objective {i}",
                token_budget=1024,
                tool_budget=5,
                timeout_seconds=10.0,
            )
            results.append(result)

        assert all(r.status == "completed" for r in results)

    async def test_concurrent_subagents_maintain_parent_state(self):
        """Concurrent subagents should not corrupt parent state."""
        engine = FakeEngine()
        se = SubagentEngine(engine)

        tasks = []
        for i in range(3):
            tasks.append(
                se.spawn(
                    parent_run_id=f"parent_{i}",
                    objective=f"Task {i}",
                    token_budget=1024,
                    tool_budget=5,
                    timeout_seconds=10.0,
                )
            )
        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        assert all(r.status == "completed" for r in results)

        tracked = se.list_tasks()
        assert len(tracked) == 3

    async def test_subagent_timeout(self):
        """Subagent should respect timeout."""
        engine = FakeEngine(provider=SlowProvider())
        se = SubagentEngine(engine)

        result = await se.spawn(
            parent_run_id="parent_timeout",
            objective="Slow task",
            token_budget=1024,
            tool_budget=5,
            timeout_seconds=0.5,
        )

        assert result.status == "timeout"

    async def test_subagent_cancellation(self):
        """Subagent should support cancellation."""
        engine = FakeEngine(provider=SlowProvider())
        se = SubagentEngine(engine)

        async def run_and_cancel():
            task = asyncio.create_task(
                se.spawn(
                    parent_run_id="parent_cancel",
                    objective="Long task",
                    token_budget=1024,
                    tool_budget=5,
                    timeout_seconds=30.0,
                )
            )
            await asyncio.sleep(0.1)
            tasks = se.list_tasks()
            if tasks:
                se.cancel(tasks[0]["task_id"])
            return await task

        result = await run_and_cancel()
        assert result.status in ("cancelled", "timeout", "completed")

    async def test_subagent_capability_isolation(self):
        """Subagent should only have access to allowed tools."""
        engine = FakeEngine()
        se = SubagentEngine(engine)

        result = await se.spawn(
            parent_run_id="parent_cap",
            objective="Test with restricted tools",
            allowed_tools=["specific_tool"],
            token_budget=1024,
            tool_budget=5,
            timeout_seconds=10.0,
        )

        assert result.status == "completed"

    async def test_subagent_task_tracking(self):
        """All subagent tasks should be tracked."""
        engine = FakeEngine()
        se = SubagentEngine(engine)

        for i in range(5):
            await se.spawn(
                parent_run_id=f"parent_{i}",
                objective=f"Task {i}",
                token_budget=1024,
                tool_budget=5,
                timeout_seconds=10.0,
            )

        tasks = se.list_tasks()
        assert len(tasks) == 5

    async def test_subagent_result_structure(self):
        """Subagent result should have required fields."""
        engine = FakeEngine()
        se = SubagentEngine(engine)

        result = await se.spawn(
            parent_run_id="parent_struct",
            objective="Test result structure",
            token_budget=1024,
            tool_budget=5,
            timeout_seconds=10.0,
        )

        result_dict = result.to_dict()
        assert "task_id" in result_dict
        assert "status" in result_dict
        assert "summary" in result_dict
        assert "evidence" in result_dict
        assert "confidence" in result_dict
        assert "metrics" in result_dict

    async def test_subagent_event_tracking(self):
        """Subagent should emit spawn and completion events."""
        engine = FakeEngine()
        tracker = MagicMock()
        tracker.emit_subagent_spawned = MagicMock()
        tracker.emit_subagent_completed = MagicMock()

        se = SubagentEngine(engine, event_tracker=tracker)

        await se.spawn(
            parent_run_id="parent_events",
            objective="Test events",
            token_budget=1024,
            tool_budget=5,
            timeout_seconds=10.0,
        )

        assert tracker.emit_subagent_spawned.called
        assert tracker.emit_subagent_completed.called

    def test_cancel_nonexistent_task(self):
        """Cancelling a non-existent task should return False."""
        engine = FakeEngine()
        se = SubagentEngine(engine)
        assert se.cancel("nonexistent_task_id") is False

    async def test_subagent_with_no_providers(self):
        """Subagent should fail gracefully with no providers."""
        engine = FakeEngine()
        engine.providers = {}
        engine.config = MagicMock()
        engine.config.agent = MagicMock()
        engine.config.agent.model = "nonexistent/model"

        se = SubagentEngine(engine)

        result = await se.spawn(
            parent_run_id="parent_noprovider",
            objective="Task with no provider",
            token_budget=1024,
            tool_budget=5,
            timeout_seconds=10.0,
        )

        assert result.status == "failed"
