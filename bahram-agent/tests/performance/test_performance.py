from __future__ import annotations

import asyncio
import time

import pytest

from bahram.core.engine import AgentEngine, AgentResponse, Message, MessageRole


class MockProvider:
    def __init__(self, delay: float = 0.0, responses=None):
        self._delay = delay
        self._responses = list(responses or [AgentResponse(content="ok")])
        self.call_count = 0
        self.total_latency = 0.0

    async def complete(self, messages, tools=None, **kwargs):
        self.call_count += 1
        start = time.time()
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        latency = time.time() - start
        self.total_latency += latency
        if self._responses:
            return self._responses.pop(0)
        return AgentResponse(content="ok")

    async def stream(self, messages, tools=None, **kwargs):
        resp = await self.complete(messages, tools, **kwargs)
        yield resp.content


class MockTool:
    def schema(self):
        return {"name": "mock", "description": "mock", "parameters": {"type": "object", "properties": {}}}

    async def execute(self, **kwargs):
        return "ok"


class TestProviderLatency:
    @pytest.mark.asyncio
    async def test_single_call_latency(self):
        engine = AgentEngine()
        provider = MockProvider(delay=0.01)
        engine.providers["test"] = provider
        engine.register_tool("mock", MockTool())

        start = time.time()
        messages = [Message(role=MessageRole.USER, content="test")]
        await engine.run(messages, model="test/model")
        latency = time.time() - start
        assert latency < 5.0
        assert provider.call_count == 1

    @pytest.mark.asyncio
    async def test_tool_call_latency(self):
        engine = AgentEngine()
        from bahram.core.engine import ToolCall
        provider = MockProvider(responses=[
            AgentResponse(
                content="",
                tool_calls=[ToolCall(id="tc1", name="mock", arguments={})],
            ),
            AgentResponse(content="done"),
        ])
        engine.providers["test"] = provider
        engine.register_tool("mock", MockTool())

        start = time.time()
        messages = [Message(role=MessageRole.USER, content="test")]
        response = await engine.run(messages, model="test/model")
        latency = time.time() - start
        assert latency < 5.0
        assert provider.call_count == 2


class TestSmartContextPerformance:
    def test_context_build_latency(self):
        from bahram.core.smart_context import SmartContextManager
        scm = SmartContextManager(max_tokens=10000)
        scm.set_system_prompt("System prompt " * 100)

        start = time.time()
        for i in range(50):
            scm.add_history("user", f"Message {i} " * 50)
            scm.add_history("assistant", f"Response {i} " * 50)
        scm.optimize()
        messages = scm.build_messages()
        latency = time.time() - start
        assert latency < 1.0
        assert len(messages) > 0

    def test_context_optimization_latency(self):
        from bahram.core.smart_context import SmartContextManager
        scm = SmartContextManager(max_tokens=1000)
        for i in range(100):
            scm.add_context(f"Context {i} " * 100, priority=i % 5)

        start = time.time()
        removed = scm.optimize()
        latency = time.time() - start
        assert latency < 0.5


class TestBudgetTracking:
    def test_budget_recording_latency(self):
        from bahram.autonomy.budget import BudgetManager
        bm = BudgetManager()

        start = time.time()
        for i in range(1000):
            bm.record_model_call(f"run_{i}", input_tokens=100, output_tokens=50)
            bm.record_tool_call(f"run_{i}")
        latency = time.time() - start
        assert latency < 1.0

    def test_budget_check_latency(self):
        from bahram.autonomy.budget import BudgetManager
        bm = BudgetManager()
        for i in range(100):
            bm.record_model_call("run1", input_tokens=100, output_tokens=50)

        start = time.time()
        for _ in range(1000):
            bm.check_budget("run1")
        latency = time.time() - start
        assert latency < 0.5


class TestEventTracking:
    def test_event_emission_latency(self):
        from bahram.autonomy.events import EventTracker
        et = EventTracker()

        start = time.time()
        for i in range(1000):
            et.emit("test_event", f"session_{i}", f"run_{i}", data={"index": i})
        latency = time.time() - start
        assert latency < 1.0

    def test_event_query_latency(self):
        from bahram.autonomy.events import EventTracker
        et = EventTracker()
        for i in range(500):
            et.emit("test_event", f"session_{i % 10}", f"run_{i}", data={"index": i})

        start = time.time()
        for _ in range(100):
            et.query_events(event_type="test_event", session_id="session_5")
        latency = time.time() - start
        assert latency < 1.0


class TestRecoveryCheckpoint:
    def test_checkpoint_latency(self):
        import tempfile
        import uuid

        from bahram.autonomy.plan import Plan, PlanStep, StepStatus
        from bahram.autonomy.recovery import RecoveryManager

        with tempfile.TemporaryDirectory() as tmpdir:
            rm = RecoveryManager(data_dir=tmpdir)
            plan_id = f"plan_{uuid.uuid4().hex[:8]}"
            plan = Plan(goal="test", id=plan_id, run_id="run1")
            for i in range(20):
                step = PlanStep(id=f"step_{i}", plan_id=plan_id, objective=f"Step {i}")
                step.status = StepStatus.COMPLETED
                plan.steps.append(step)

            start = time.time()
            for _ in range(100):
                rm.checkpoint(run_id="run1", plan=plan, context_summary="test")
            latency = time.time() - start
            assert latency < 2.0
