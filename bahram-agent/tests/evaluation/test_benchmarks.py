from __future__ import annotations

import asyncio
import json
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bahram.autonomy.budget import BudgetConfig, BudgetManager
from bahram.autonomy.events import EventTracker
from bahram.autonomy.executor import PlanExecutor
from bahram.autonomy.jobs import Job, JobEngine, JobPriority, JobStatus
from bahram.autonomy.learning import LearningEngine, Lesson, SkillCandidate
from bahram.autonomy.plan import Plan, PlanStatus, PlanStep, StepStatus
from bahram.autonomy.planner import Planner
from bahram.autonomy.recovery import RecoveryManager
from bahram.autonomy.replanner import Replanner
from bahram.autonomy.skill_lifecycle import SkillLifecycle
from bahram.autonomy.subagent import SubagentEngine, SubagentResult
from bahram.autonomy.verification import VerificationEngine, VerificationResult


def make_mock_provider(responses=None):
    mock = AsyncMock()
    if responses:
        mock.complete = AsyncMock(side_effect=responses)
    else:
        resp = MagicMock()
        resp.content = '{"strategy":"test","rationale":"test","steps":[{"id":"s1","objective":"step1","dependencies":[],"required_tools":[]}]}'
        resp.tool_calls = []
        mock.complete = AsyncMock(return_value=resp)
    return mock


# ── AUTO-01: Simple Direct Task ────────────────────────────

class TestAUTO01_SimpleDirectTask:
    @pytest.mark.asyncio
    async def test_simple_plan_creation(self):
        planner = Planner()
        plan = await planner.create_plan("list files in current directory")
        assert plan.status == PlanStatus.READY
        assert len(plan.steps) > 0
        for step in plan.steps:
            assert step.plan_id == plan.id

    @pytest.mark.asyncio
    async def test_simple_plan_has_verification(self):
        planner = Planner()
        plan = await planner.create_plan("fix the login bug")
        has_verification = any(
            len(s.verification_criteria) > 0 for s in plan.steps
        )
        assert has_verification


# ── AUTO-02: Multi-Tool Task ───────────────────────────────

class TestAUTO02_MultiToolTask:
    @pytest.mark.asyncio
    async def test_multi_tool_plan(self):
        planner = Planner()
        plan = await planner.create_plan(
            "read the config file, modify the database settings, and write it back"
        )
        all_tools = set()
        for step in plan.steps:
            all_tools.update(step.required_tools)
        assert len(all_tools) >= 1

    @pytest.mark.asyncio
    async def test_plan_with_tool_requirements(self):
        planner = Planner()
        plan = await planner.create_plan("create a new Python file and test it")
        for step in plan.steps:
            assert isinstance(step.required_tools, list)


# ── AUTO-03: Multi-Step Plan ───────────────────────────────

class TestAUTO03_MultiStepPlan:
    @pytest.mark.asyncio
    async def test_multi_step_plan_structure(self):
        planner = Planner()
        plan = await planner.create_plan(
            "investigate the failing test, identify the root cause, fix it, and verify"
        )
        assert len(plan.steps) >= 3
        assert plan.strategy != ""
        assert plan.success_criteria is not None

    @pytest.mark.asyncio
    async def test_plan_dependencies_form_dag(self):
        planner = Planner()
        plan = await planner.create_plan(
            "fix bug: investigate, fix, test, deploy"
        )
        errors = plan.validate_dependencies()
        assert errors == []
        cycles = plan.detect_cycles()
        assert cycles is None


# ── AUTO-04: Plan Dependency DAG ───────────────────────────

class TestAUTO04_PlanDAG:
    def test_dag_with_parallel_steps(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="analyze"))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="research_a"))
        plan.add_step(PlanStep(id="s3", plan_id="p1", objective="research_b"))
        plan.add_step(PlanStep(id="s4", plan_id="p1", objective="synthesize",
                               dependencies=["s2", "s3"]))
        plan.add_step(PlanStep(id="s5", plan_id="p1", objective="verify",
                               dependencies=["s1", "s4"]))

        ready = plan.get_ready_steps()
        assert len(ready) == 3
        assert {s.id for s in ready} == {"s1", "s2", "s3"}

        plan.steps[0].status = StepStatus.COMPLETED
        ready = plan.get_ready_steps()
        ready_ids = {s.id for s in ready}
        assert "s5" not in ready_ids or "s4" in [s.id for s in plan.get_completed_steps()]

    def test_dag_cycle_detection(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a", dependencies=["s3"]))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="b", dependencies=["s1"]))
        plan.add_step(PlanStep(id="s3", plan_id="p1", objective="c", dependencies=["s2"]))
        cycles = plan.detect_cycles()
        assert cycles is not None


# ── AUTO-05: Parallel Safe Steps ──────────────────────────

class TestAUTO05_ParallelSteps:
    def test_independent_steps_can_run_in_parallel(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        for i in range(5):
            plan.add_step(PlanStep(id=f"s{i}", plan_id="p1", objective=f"step{i}"))
        ready = plan.get_ready_steps()
        assert len(ready) == 5

    def test_dependent_steps_wait(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="first"))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="second", dependencies=["s1"]))
        plan.add_step(PlanStep(id="s3", plan_id="p1", objective="third", dependencies=["s2"]))
        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].id == "s1"


# ── AUTO-06: Tool Failure → Retry ─────────────────────────

class TestAUTO06_ToolFailureRetry:
    @pytest.mark.asyncio
    async def test_timeout_triggers_retry(self):
        planner = Planner()
        verification = VerificationEngine()
        replanner = Replanner(planner, verification)

        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="step1"))

        await replanner.handle_step_failure(plan, plan.steps[0], "timeout after 30s")
        assert plan.steps[0].status == StepStatus.PENDING
        assert plan.steps[0].attempt_count == 1

    @pytest.mark.asyncio
    async def test_network_error_triggers_retry(self):
        planner = Planner()
        verification = VerificationEngine()
        replanner = Replanner(planner, verification)

        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="step1"))

        await replanner.handle_step_failure(plan, plan.steps[0], "connection refused")
        assert plan.steps[0].status == StepStatus.PENDING


# ── AUTO-07: Tool Failure → Replan ────────────────────────

class TestAUTO07_ToolFailureReplan:
    @pytest.mark.asyncio
    async def test_permission_denial_modifies_step(self):
        planner = Planner()
        verification = VerificationEngine()
        replanner = Replanner(planner, verification)

        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="step1"))

        await replanner.handle_step_failure(plan, plan.steps[0], "permission denied")
        assert plan.steps[0].status == StepStatus.REPLANNED
        assert len(plan.steps) == 2
        assert plan.steps[1].objective.startswith("Modified:")

    @pytest.mark.asyncio
    async def test_missing_resource_inserts_prereq(self):
        planner = Planner()
        verification = VerificationEngine()
        replanner = Replanner(planner, verification)

        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="step1"))

        await replanner.handle_step_failure(plan, plan.steps[0], "file not found: config.yaml")
        assert any("prereq" in s.id for s in plan.steps)


# ── AUTO-08: Verification Failure → Repair ────────────────

class TestAUTO08_VerificationRepair:
    @pytest.mark.asyncio
    async def test_verification_failure_triggers_retry(self):
        planner = Planner()
        verification = VerificationEngine()
        replanner = Replanner(planner, verification)

        plan = Plan(id="p1", run_id="r1", goal="test")
        step = PlanStep(id="s1", plan_id="p1", objective="step1", max_attempts=3)
        plan.add_step(step)

        vr = VerificationResult(passed=False, verification_type="command", details="exit code 1")
        await replanner.handle_verification_failure(plan, step, [vr])
        assert step.status == StepStatus.PENDING
        assert step.attempt_count == 1

    @pytest.mark.asyncio
    async def test_multiple_verification_failures(self):
        planner = Planner()
        verification = VerificationEngine()
        replanner = Replanner(planner, verification)

        plan = Plan(id="p1", run_id="r1", goal="test")
        step = PlanStep(id="s1", plan_id="p1", objective="step1", max_attempts=2)
        plan.add_step(step)

        vrs = [
            VerificationResult(passed=False, verification_type="command", details="fail1"),
            VerificationResult(passed=False, verification_type="file_exists", details="fail2"),
        ]
        await replanner.handle_verification_failure(plan, step, vrs)
        assert step.status == StepStatus.PENDING


# ── AUTO-09: Subagent Delegation ──────────────────────────

class TestAUTO09_SubagentDelegation:
    @pytest.mark.asyncio
    async def test_spawn_and_complete(self):
        from bahram.core.engine import AgentEngine

        engine = AgentEngine()
        mock_provider = AsyncMock()
        resp = MagicMock()
        resp.content = "Research complete: found 3 relevant files"
        resp.tool_calls = []
        mock_provider.complete = AsyncMock(return_value=resp)
        engine.register_provider("mock", mock_provider)

        subagent = SubagentEngine(engine)
        result = await subagent.spawn(
            parent_run_id="r1",
            objective="research the codebase",
            model="mock/test",
        )
        assert result.status == "completed"
        assert "Research complete" in result.summary
        assert result.metrics["iterations"] >= 1

    @pytest.mark.asyncio
    async def test_subagent_tool_filtering(self):
        from bahram.core.engine import AgentEngine

        engine = AgentEngine()
        mock_provider = AsyncMock()
        resp = MagicMock()
        resp.content = "done"
        resp.tool_calls = []
        mock_provider.complete = AsyncMock(return_value=resp)
        engine.register_provider("mock", mock_provider)

        subagent = SubagentEngine(engine)
        result = await subagent.spawn(
            parent_run_id="r1",
            objective="test",
            allowed_tools=["read"],
            model="mock/test",
        )
        assert result.status == "completed"


# ── AUTO-10: Parallel Subagents ───────────────────────────

class TestAUTO10_ParallelSubagents:
    @pytest.mark.asyncio
    async def test_parallel_subagent_spawn(self):
        from bahram.core.engine import AgentEngine

        engine = AgentEngine()
        mock_provider = AsyncMock()
        resp = MagicMock()
        resp.content = "done"
        resp.tool_calls = []
        mock_provider.complete = AsyncMock(return_value=resp)
        engine.register_provider("mock", mock_provider)

        subagent = SubagentEngine(engine)
        tasks = [
            subagent.spawn(parent_run_id="r1", objective=f"task{i}", model="mock/test")
            for i in range(3)
        ]
        results = await asyncio.gather(*tasks)
        assert all(r.status == "completed" for r in results)


# ── AUTO-11: Persistent Background Job ────────────────────

class TestAUTO11_BackgroundJob:
    @pytest.mark.asyncio
    async def test_job_persists_across_restarts(self, tmp_path):
        engine1 = JobEngine(data_dir=str(tmp_path))
        job = await engine1.enqueue(
            "test_job", "r1", "s1",
            payload={"type": "test_job", "data": "important"},
        )

        engine2 = JobEngine(data_dir=str(tmp_path))
        loaded = engine2.get_job(job.id)
        assert loaded is not None
        assert loaded.payload["data"] == "important"
        assert loaded.state == JobStatus.QUEUED

    @pytest.mark.asyncio
    async def test_job_handler_completes(self, tmp_path):
        engine = JobEngine(data_dir=str(tmp_path))

        async def handler(job_id, run_id, session_id, **kwargs):
            return "job_done"

        engine.register_handler("do_work", handler)
        job = await engine.enqueue("do_work", "r1", "s1", payload={"type": "do_work"})
        await engine.start_job(job)
        await asyncio.sleep(0.5)

        loaded = engine.get_job(job.id)
        assert loaded.state == JobStatus.COMPLETED
        assert loaded.result == "job_done"


# ── AUTO-12: Job Crash → Resume ───────────────────────────

class TestAUTO12_JobResume:
    @pytest.mark.asyncio
    async def test_interrupted_job_detected(self, tmp_path):
        engine = JobEngine(data_dir=str(tmp_path))
        job = await engine.enqueue("test", "r1", "s1", payload={"type": "test"})
        job.state = JobStatus.RUNNING
        job.started_at = time.time()
        engine._save_job(job)

        engine2 = JobEngine(data_dir=str(tmp_path))
        pending = engine2.list_jobs(state=JobStatus.RUNNING)
        assert len(pending) >= 1


# ── AUTO-13: Memory Reuse ─────────────────────────────────

class TestAUTO13_MemoryReuse:
    @pytest.mark.asyncio
    async def test_memory_informs_planning(self):
        planner = Planner()
        plan = await planner.create_plan(
            "fix the login bug",
            memory_context="Previous fix: the issue was in auth.py line 42",
        )
        assert plan.status == PlanStatus.READY
        assert len(plan.steps) > 0

    @pytest.mark.asyncio
    async def test_skill_context_in_planning(self):
        planner = Planner()
        plan = await planner.create_plan(
            "run tests",
            skill_context="Skill: pytest_runner - use pytest -q for fast tests",
        )
        assert plan.status == PlanStatus.READY


# ── AUTO-14: Learning → Skill Generation ──────────────────

class TestAUTO14_LearningSkillGeneration:
    @pytest.mark.asyncio
    async def test_learning_extracts_lessons(self, tmp_path):
        engine = LearningEngine(data_dir=str(tmp_path))
        analysis = await engine.analyze_outcome(
            run_id="r1", goal="fix bug",
            trajectory_steps=[{"step": 1}],
            tool_results=[{"tool": "bash", "success": False, "error": "command not found"}],
            success=False,
        )
        assert len(analysis["lessons_extracted"]) > 0

    @pytest.mark.asyncio
    async def test_skill_generated_from_lessons(self, tmp_path):
        engine = LearningEngine(data_dir=str(tmp_path))
        engine._lessons["l1"] = Lesson(
            id="l1", content="pytest requires -q flag", scope="testing",
            source_run="r1", confidence=0.6,
        )
        engine._save()

        skill = await engine.generate_skill(["l1"])
        assert skill is not None
        assert skill.status == "candidate"

    @pytest.mark.asyncio
    async def test_skill_validation_promotion(self, tmp_path):
        engine = LearningEngine(data_dir=str(tmp_path))
        skill = SkillCandidate(
            id="s1", name="test", description="test", instructions="test",
            triggers=["test"], usage_count=5, success_count=4, failure_count=1,
            confidence=0.5,
        )
        engine._skills["s1"] = skill
        engine._save()

        lifecycle = SkillLifecycle(engine)
        status = await lifecycle.validate("s1")
        assert status in ("tested", "trusted")


# ── AUTO-15: Skill Reuse ──────────────────────────────────

class TestAUTO15_SkillReuse:
    @pytest.mark.asyncio
    async def test_skill_retrieval_by_trigger(self, tmp_path):
        engine = LearningEngine(data_dir=str(tmp_path))
        skill = SkillCandidate(
            id="s1", name="pytest_skill", description="run tests", instructions="use pytest -q",
            triggers=["pytest", "test"], status="trusted", confidence=0.8,
        )
        engine._skills["s1"] = skill

        lifecycle = SkillLifecycle(engine)
        trusted = lifecycle.get_trusted_skills()
        assert len(trusted) == 1
        assert "pytest" in trusted[0].triggers

    @pytest.mark.asyncio
    async def test_skill_usage_tracking(self, tmp_path):
        engine = LearningEngine(data_dir=str(tmp_path))
        skill = SkillCandidate(
            id="s1", name="test", description="test", instructions="test",
            triggers=["test"], confidence=0.5,
        )
        engine._skills["s1"] = skill

        lifecycle = SkillLifecycle(engine)
        await lifecycle.record_usage("s1", success=True)
        await lifecycle.record_usage("s1", success=True)
        await lifecycle.record_usage("s1", success=False)

        assert skill.success_count == 2
        assert skill.failure_count == 1


# ── AUTO-16: Provider Failure → Fallback ──────────────────

class TestAUTO16_ProviderFallback:
    @pytest.mark.asyncio
    async def test_fallback_provider_tries_chain(self):
        from bahram.core.engine import AgentResponse
        from bahram.providers.base import BaseProvider
        from bahram.providers.fallback import FallbackProvider

        class MockProvider(BaseProvider):
            def __init__(self, response=None, error=None):
                self._response = response
                self._error = error

            async def _call_api(self, messages, system_msg=None, tools=None, model=None, temperature=0.7, max_tokens=4096, **kwargs):
                if self._error:
                    raise self._error
                return self._response

        primary = MockProvider(error=Exception("primary failed"))
        fallback = MockProvider(response=AgentResponse(content="fallback worked"))

        fp = FallbackProvider(primary, [fallback])
        result = await fp.complete([], [])
        assert result.content == "fallback worked"

    @pytest.mark.asyncio
    async def test_all_providers_fail(self):
        from bahram.providers.base import BaseProvider
        from bahram.providers.fallback import FallbackProvider

        class MockProvider(BaseProvider):
            def __init__(self, error):
                self._error = error

            async def _call_api(self, messages, system_msg=None, tools=None, model=None, temperature=0.7, max_tokens=4096, **kwargs):
                raise self._error

        primary = MockProvider(Exception("primary failed"))
        fallback = MockProvider(Exception("fallback failed"))

        fp = FallbackProvider(primary, [fallback])
        with pytest.raises(Exception, match="All providers failed"):
            await fp.complete([], [])


# ── AUTO-17: Context Compression ──────────────────────────

class TestAUTO17_ContextCompression:
    def test_budget_warning_at_threshold(self):
        config = BudgetConfig(max_total_tokens=1000, warning_threshold=0.8)
        manager = BudgetManager(config)
        warnings = manager.record_model_call("r1", "", 600, 300)
        assert len(warnings) > 0
        assert "token" in warnings[0].lower()

    def test_budget_enforcement(self):
        config = BudgetConfig(max_total_tokens=100)
        manager = BudgetManager(config)
        manager.record_model_call("r1", "", 50, 60)
        check = manager.check_budget("r1")
        assert not check["can_continue"]
        assert "total_tokens" in check["exceeded"]


# ── AUTO-18: Budget Exhaustion ────────────────────────────

class TestAUTO18_BudgetExhaustion:
    def test_budget_exceeded_stops_execution(self):
        config = BudgetConfig(max_model_calls=5)
        manager = BudgetManager(config)
        for _ in range(5):
            manager.record_model_call("r1", "", 10, 5)
        check = manager.check_budget("r1")
        assert not check["can_continue"]
        assert "model_calls" in check["exceeded"]

    def test_tool_budget_exceeded(self):
        config = BudgetConfig(max_tool_calls=3)
        manager = BudgetManager(config)
        for _ in range(3):
            manager.record_tool_call("r1")
        check = manager.check_budget("r1")
        assert not check["can_continue"]
        assert "tool_calls" in check["exceeded"]


# ── AUTO-19: Cancellation ────────────────────────────────

class TestAUTO19_Cancellation:
    @pytest.mark.asyncio
    async def test_engine_cancellation(self):
        from bahram.core.engine import AgentEngine

        engine = AgentEngine()
        engine.cancel()
        assert engine._cancel_event.is_set()
        engine.reset_cancel()
        assert not engine._cancel_event.is_set()

    @pytest.mark.asyncio
    async def test_subagent_cancellation(self):
        from bahram.core.engine import AgentEngine

        engine = AgentEngine()
        subagent = SubagentEngine(engine)
        event = asyncio.Event()
        subagent._cancel_events["task1"] = event
        subagent.cancel("task1")
        assert event.is_set()

    @pytest.mark.asyncio
    async def test_job_cancellation(self, tmp_path):
        engine = JobEngine(data_dir=str(tmp_path))

        async def slow_handler(job_id, run_id, session_id, **kwargs):
            await asyncio.sleep(100)
            return "done"

        engine.register_handler("slow", slow_handler)
        job = await engine.enqueue("slow", "r1", "s1", payload={"type": "slow"})
        await engine.start_job(job)
        await asyncio.sleep(0.1)
        cancelled = await engine.cancel_job(job.id)
        assert cancelled


# ── AUTO-20: Long-Running Autonomous Task ─────────────────

class TestAUTO20_LongRunningTask:
    @pytest.mark.asyncio
    async def test_full_plan_lifecycle(self):
        planner = Planner()
        plan = await planner.create_plan(
            "investigate bug, fix it, test, verify, summarize"
        )

        verification = VerificationEngine()
        for step in plan.steps:
            step.status = StepStatus.RUNNING
            step.started_at = time.time()

            vr = await verification.verify(
                "ok",
                [{"type": "content_check", "params": {"contains": "ok"}}]
            )
            if all(r.passed for r in vr):
                step.status = StepStatus.COMPLETED
            else:
                step.status = StepStatus.FAILED
            step.completed_at = time.time()

        progress = plan.get_progress()
        assert progress["completed"] == len(plan.steps)
        assert plan.is_complete()

    @pytest.mark.asyncio
    async def test_plan_with_replanning_midway(self):
        planner = Planner()
        plan = await planner.create_plan("step1, step2, step3, verify")
        replanner = Replanner(planner, VerificationEngine())

        plan.steps[0].status = StepStatus.COMPLETED
        plan.steps[1].status = StepStatus.COMPLETED

        plan = await replanner.handle_step_failure(
            plan, plan.steps[2], "tool failed: timeout"
        )

        assert plan.steps[2].status == StepStatus.PENDING
        assert plan.steps[0].status == StepStatus.COMPLETED
        assert plan.steps[1].status == StepStatus.COMPLETED


# ── Event Correlation Tests ───────────────────────────────

class TestEventCorrelation:
    def test_all_events_have_ids(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        event = tracker.emit_plan_created("s1", "r1", "p1")
        assert event.session_id == "s1"
        assert event.run_id == "r1"
        assert event.plan_id == "p1"

    def test_trace_by_run_id(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        tracker.emit("e1", run_id="r1")
        tracker.emit("e2", run_id="r1")
        tracker.emit("e3", run_id="r2")
        trace = tracker.get_trace("r1")
        assert len(trace) == 2


# ── State Invariant Tests ─────────────────────────────────

class TestStateInvariants:
    def test_plan_completeness_requires_all_steps(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="b"))
        plan.steps[0].status = StepStatus.COMPLETED
        assert plan.is_complete() is False

    def test_cannot_complete_with_pending_steps(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="b"))
        assert plan.is_complete() is False

    @pytest.mark.asyncio
    async def test_skill_cannot_promote_without_usage(self, tmp_path):
        engine = LearningEngine(data_dir=str(tmp_path))
        skill = SkillCandidate(
            id="s1", name="test", description="test", instructions="test",
            triggers=["test"], usage_count=0, confidence=0.3,
        )
        engine._skills["s1"] = skill
        engine._save()

        lifecycle = SkillLifecycle(engine)
        status = await lifecycle.validate("s1")
        assert status == "candidate"

    def test_budget_prevents_runaway(self):
        config = BudgetConfig(max_total_tokens=100)
        manager = BudgetManager(config)
        manager.record_model_call("r1", "", 60, 50)
        check = manager.check_budget("r1")
        assert not check["can_continue"]
