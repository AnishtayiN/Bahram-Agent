"""Phase 10: Resource exhaustion tests.

Tests that the system handles resource exhaustion gracefully:
repeated model calls, tool calls, huge outputs, recursive subagents.
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from bahram.autonomy.budget import BudgetConfig, BudgetManager
from bahram.core.engine import AgentEngine, AgentResponse, RunState, ToolCall


class FakeProvider:
    def __init__(self, response=None):
        self._response = response or AgentResponse(content="OK", state=RunState.COMPLETED)
        self.call_count = 0

    async def complete(self, messages, tools=None, **kwargs):
        self.call_count += 1
        return self._response

    async def stream(self, messages, tools=None, **kwargs):
        yield "chunk"


class CountingTool:
    def __init__(self):
        self.call_count = 0

    async def execute(self, **kwargs):
        self.call_count += 1
        return f"result_{self.call_count}"

    def schema(self):
        return {
            "name": "counting_tool",
            "description": "Counts calls",
            "parameters": {"type": "object", "properties": {}},
        }


class LoopingProvider:
    """Provider that always requests a tool call (infinite loop scenario)."""

    def __init__(self):
        self.call_count = 0

    async def complete(self, messages, tools=None, **kwargs):
        self.call_count += 1
        if self.call_count > 1:
            await asyncio.sleep(0.5)
        return AgentResponse(
            content="calling tool",
            tool_calls=[ToolCall(id=f"tc_{self.call_count}", name="counting_tool", arguments={})],
        )

    async def stream(self, messages, tools=None, **kwargs):
        yield "chunk"


class TestResourceExhaustion:
    """Verify bounded behavior under resource pressure."""

    def test_budget_enforcement_stops_execution(self):
        """Budget manager should stop execution when limits are exceeded."""
        config = BudgetConfig(
            max_model_calls=3,
            max_tool_calls=5,
            max_total_tokens=1000,
        )
        bm = BudgetManager(config)

        run_id = "exhaustion_test"

        for _ in range(3):
            bm.record_model_call(run_id, input_tokens=100, output_tokens=100)

        result = bm.check_budget(run_id)
        assert not result["can_continue"]
        assert "model_calls" in result["exceeded"]

    def test_tool_call_budget_enforcement(self):
        """Tool call budget should be enforced."""
        config = BudgetConfig(max_tool_calls=3)
        bm = BudgetManager(config)

        run_id = "tool_exhaustion"

        for _ in range(3):
            bm.record_tool_call(run_id)

        result = bm.check_budget(run_id)
        assert not result["can_continue"]
        assert "tool_calls" in result["exceeded"]

    def test_token_budget_enforcement(self):
        """Token budget should be enforced."""
        config = BudgetConfig(max_total_tokens=500)
        bm = BudgetManager(config)

        run_id = "token_exhaustion"

        bm.record_model_call(run_id, input_tokens=300, output_tokens=300)

        result = bm.check_budget(run_id)
        assert not result["can_continue"]
        assert "total_tokens" in result["exceeded"]

    def test_budget_warning_threshold(self):
        """Warnings should be emitted before hard limits."""
        config = BudgetConfig(
            max_model_calls=10,
            warning_threshold=0.8,
        )
        bm = BudgetManager(config)

        run_id = "warning_test"

        for _ in range(8):
            warnings = bm.record_model_call(run_id, input_tokens=10, output_tokens=10)

        assert len(warnings) > 0

    def test_budget_reset(self):
        """Budget reset should clear all tracked usage."""
        config = BudgetConfig(max_model_calls=5)
        bm = BudgetManager(config)

        run_id = "reset_test"

        for _ in range(5):
            bm.record_model_call(run_id, input_tokens=10, output_tokens=10)

        result = bm.check_budget(run_id)
        assert not result["can_continue"]

        bm.reset_run(run_id)

        result = bm.check_budget(run_id)
        assert result["can_continue"]

    def test_budget_isolation_per_run(self):
        """Budgets should be isolated per run."""
        config = BudgetConfig(max_model_calls=3)
        bm = BudgetManager(config)

        for _ in range(3):
            bm.record_model_call("run_a", input_tokens=10, output_tokens=10)

        result_a = bm.check_budget("run_a")
        assert not result_a["can_continue"]

        result_b = bm.check_budget("run_b")
        assert result_b["can_continue"]

    def test_engine_max_iterations_stops(self):
        """Engine should stop at max_iterations."""
        provider = LoopingProvider()

        engine = AgentEngine()
        engine.register_provider("test", provider)
        tool = CountingTool()
        engine.register_tool("counting_tool", tool)

        engine.config = MagicMock()
        engine.config.agent.max_iterations = 3
        engine.config.agent.model = "test/model"
        engine.config.agent.max_tool_calls = 50
        engine.config.agent.max_runtime_seconds = 300.0
        engine.config.tools.bash_timeout = 10

        msg = MagicMock()
        msg.role = MagicMock()
        msg.role.value = "user"
        msg.content = "test"

        result = asyncio.run(
            engine.run([msg], model="test/model")
        )

        assert provider.call_count <= 4

    def test_engine_max_tool_calls_stops(self):
        """Engine should stop at max_tool_calls."""
        provider = LoopingProvider()

        engine = AgentEngine()
        engine.register_provider("test", provider)
        tool = CountingTool()
        engine.register_tool("counting_tool", tool)

        engine.config = MagicMock()
        engine.config.agent.max_iterations = 100
        engine.config.agent.model = "test/model"
        engine.config.agent.max_tool_calls = 3
        engine.config.agent.max_runtime_seconds = 300.0
        engine.config.tools.bash_timeout = 10

        msg = MagicMock()
        msg.role = MagicMock()
        msg.role.value = "user"
        msg.content = "test"

        result = asyncio.run(
            engine.run([msg], model="test/model")
        )

        assert tool.call_count <= 4

    def test_budget_subagent_tracking(self):
        """Subagent calls should be tracked in budget."""
        config = BudgetConfig(max_subagent_calls=2)
        bm = BudgetManager(config)

        run_id = "subagent_test"

        bm.record_subagent_call(run_id)
        bm.record_subagent_call(run_id)

        result = bm.check_budget(run_id)
        assert not result["can_continue"]
        assert "subagent_calls" in result["exceeded"]

    def test_engine_cancellation_stops_loop(self):
        """Engine cancellation should stop the execution loop immediately."""
        import threading

        provider = LoopingProvider()

        engine = AgentEngine()
        engine.register_provider("test", provider)
        tool = CountingTool()
        engine.register_tool("counting_tool", tool)

        engine.config = MagicMock()
        engine.config.agent.max_iterations = 100
        engine.config.agent.model = "test/model"
        engine.config.agent.max_tool_calls = 100
        engine.config.agent.max_runtime_seconds = 300.0
        engine.config.tools.bash_timeout = 10

        msg = MagicMock()
        msg.role = MagicMock()
        msg.role.value = "user"
        msg.content = "test"

        def cancel_soon():
            import time
            time.sleep(0.2)
            engine._cancel_event.set()

        t = threading.Thread(target=cancel_soon)
        t.start()

        result = asyncio.run(
            engine.run([msg], model="test/model")
        )

        t.join(timeout=1)

        assert result.state == RunState.CANCELLED

    def test_all_usage_tracking(self):
        """get_all_usage should return all tracked budgets."""
        bm = BudgetManager()

        bm.record_model_call("run_1", input_tokens=100, output_tokens=50)
        bm.record_model_call("run_2", input_tokens=200, output_tokens=100)
        bm.record_tool_call("run_1")

        usage = bm.get_all_usage()

        assert "runs" in usage
        assert "run_1" in usage["runs"]
        assert "run_2" in usage["runs"]
        assert usage["runs"]["run_1"]["model_calls"] == 1
        assert usage["runs"]["run_2"]["model_calls"] == 1
