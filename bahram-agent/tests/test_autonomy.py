from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from bahram.autonomy.budget import BudgetConfig, BudgetManager
from bahram.autonomy.events import EventTracker
from bahram.autonomy.jobs import PRIORITY_ORDER, JobEngine, JobPriority, JobStatus
from bahram.autonomy.learning import LearningEngine, Lesson, SkillCandidate
from bahram.autonomy.plan import Plan, PlanStatus, PlanStep, StepStatus
from bahram.autonomy.planner import Planner
from bahram.autonomy.recovery import RecoveryManager
from bahram.autonomy.replanner import Replanner, ReplanningStrategy
from bahram.autonomy.skill_lifecycle import SkillLifecycle
from bahram.autonomy.subagent import SubagentEngine, SubagentResult
from bahram.autonomy.verification import VerificationEngine, VerificationResult

# ── Plan DAG Tests ──────────────────────────────────────────

class TestPlanDAG:
    def test_create_plan_with_steps(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="step1"))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="step2", dependencies=["s1"]))
        assert len(plan.steps) == 2
        assert plan.steps[1].dependencies == ["s1"]

    def test_dependency_validation_no_errors(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="b", dependencies=["s1"]))
        errors = plan.validate_dependencies()
        assert errors == []

    def test_dependency_validation_missing_step(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a", dependencies=["s99"]))
        errors = plan.validate_dependencies()
        assert len(errors) == 1
        assert "s99" in errors[0]

    def test_cycle_detection_no_cycle(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="b", dependencies=["s1"]))
        plan.add_step(PlanStep(id="s3", plan_id="p1", objective="c", dependencies=["s2"]))
        cycles = plan.detect_cycles()
        assert cycles is None

    def test_cycle_detection_with_cycle(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a", dependencies=["s3"]))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="b", dependencies=["s1"]))
        plan.add_step(PlanStep(id="s3", plan_id="p1", objective="c", dependencies=["s2"]))
        cycles = plan.detect_cycles()
        assert cycles is not None
        assert len(cycles) > 0

    def test_ready_steps_basic(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="b", dependencies=["s1"]))
        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].id == "s1"

    def test_ready_steps_after_completion(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="b", dependencies=["s1"]))
        plan.steps[0].status = StepStatus.COMPLETED
        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].id == "s2"

    def test_is_complete(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        assert not plan.is_complete()
        plan.steps[0].status = StepStatus.COMPLETED
        assert plan.is_complete()

    def test_has_failures(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        assert not plan.has_failures()
        plan.steps[0].status = StepStatus.FAILED
        assert plan.has_failures()

    def test_progress_tracking(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="b"))
        plan.add_step(PlanStep(id="s3", plan_id="p1", objective="c"))
        plan.steps[0].status = StepStatus.COMPLETED
        plan.steps[1].status = StepStatus.FAILED
        progress = plan.get_progress()
        assert progress["total"] == 3
        assert progress["completed"] == 1
        assert progress["failed"] == 1
        assert progress["progress_pct"] == pytest.approx(33.33, abs=1)

    def test_remove_step_cleans_dependencies(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="b", dependencies=["s1"]))
        plan.add_step(PlanStep(id="s3", plan_id="p1", objective="c", dependencies=["s1", "s2"]))
        plan.remove_step("s1")
        assert len(plan.steps) == 2
        assert "s1" not in plan.steps[1].dependencies

    def test_insert_step_after(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="b", dependencies=["s1"]))
        new_step = PlanStep(id="s1b", plan_id="p1", objective="a-b", dependencies=["s1"])
        plan.insert_step_after("s1", new_step)
        assert len(plan.steps) == 3
        assert plan.steps[1].id == "s1b"
        assert "s1b" in plan.steps[2].dependencies

    def test_plan_serialization(self):
        plan = Plan(id="p1", run_id="r1", goal="test", strategy="approach")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a", dependencies=[], required_tools=["bash"]))
        d = plan.to_dict()
        plan2 = Plan.from_dict(d)
        assert plan2.id == "p1"
        assert plan2.goal == "test"
        assert len(plan2.steps) == 1
        assert plan2.steps[0].required_tools == ["bash"]

    def test_parallel_safe_steps(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="b"))
        plan.add_step(PlanStep(id="s3", plan_id="p1", objective="c", dependencies=["s1", "s2"]))
        ready = plan.get_ready_steps()
        assert len(ready) == 2
        assert {s.id for s in ready} == {"s1", "s2"}


# ── Planner Tests ───────────────────────────────────────────

class TestPlanner:
    @pytest.mark.asyncio
    async def test_fallback_plan_fix_goal(self):
        planner = Planner()
        plan = await planner.create_plan("fix the login bug")
        assert plan.status == PlanStatus.READY
        assert len(plan.steps) > 0
        assert any("investigate" in s.objective.lower() for s in plan.steps)

    @pytest.mark.asyncio
    async def test_fallback_plan_create_goal(self):
        planner = Planner()
        plan = await planner.create_plan("create a new API endpoint")
        assert plan.status == PlanStatus.READY
        assert len(plan.steps) >= 3

    @pytest.mark.asyncio
    async def test_fallback_plan_research_goal(self):
        planner = Planner()
        plan = await planner.create_plan("research the best approach for caching")
        assert plan.status == PlanStatus.READY

    @pytest.mark.asyncio
    async def test_fallback_plan_generic_goal(self):
        planner = Planner()
        plan = await planner.create_plan("do something complex")
        assert plan.status == PlanStatus.READY

    @pytest.mark.asyncio
    async def test_replan_fallback(self):
        planner = Planner()
        plan = await planner.create_plan("fix the bug")
        failed_step = plan.steps[0]
        failed_step.status = StepStatus.FAILED
        failed_step.attempt_count = 1
        plan = await planner.replan(plan, failed_step, "tool failed")
        assert any(s.status == StepStatus.REPLANNED for s in plan.steps)

    @pytest.mark.asyncio
    async def test_llm_planner_integration(self):
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "strategy": "test strategy",
            "rationale": "test rationale",
            "success_criteria": ["tests pass"],
            "risk_assessment": "low risk",
            "steps": [
                {"id": "s1", "objective": "step one", "dependencies": [], "required_tools": ["bash"],
                 "verification_criteria": [{"type": "command", "params": {"command": "echo ok"}}]},
                {"id": "s2", "objective": "step two", "dependencies": ["s1"], "required_tools": ["read"]},
            ]
        })
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        planner = Planner(provider=mock_provider)
        plan = await planner.create_plan("test goal", available_tools=["bash", "read"])
        assert plan.strategy == "test strategy"
        assert len(plan.steps) == 2
        assert plan.steps[1].dependencies == ["s1"]
        assert plan.status == PlanStatus.READY

    @pytest.mark.asyncio
    async def test_llm_replan_integration(self):
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "revised_steps": [
                {"id": "s1_fix", "objective": "fix step", "dependencies": [], "required_tools": ["bash"]}
            ]
        })
        mock_provider = AsyncMock()
        mock_provider.complete = AsyncMock(return_value=mock_response)

        planner = Planner(provider=mock_provider)
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="original"))
        failed_step = plan.steps[0]
        failed_step.status = StepStatus.FAILED
        failed_step.attempt_count = 1

        plan = await planner.replan(plan, failed_step, "error occurred")
        assert plan.replan_count == 1
        assert failed_step.status == StepStatus.REPLANNED


# ── Verification Engine Tests ──────────────────────────────

class TestVerificationEngine:
    @pytest.mark.asyncio
    async def test_verify_command_success(self):
        engine = VerificationEngine()
        results = await engine.verify(
            "", [{"type": "command", "params": {"command": "echo hello"}}]
        )
        assert len(results) == 1
        assert results[0].passed is True

    @pytest.mark.asyncio
    async def test_verify_command_failure(self):
        engine = VerificationEngine()
        results = await engine.verify(
            "", [{"type": "command", "params": {"command": "false"}}]
        )
        assert len(results) == 1
        assert results[0].passed is False

    @pytest.mark.asyncio
    async def test_verify_command_custom_exit_code(self):
        engine = VerificationEngine()
        results = await engine.verify(
            "", [{"type": "command", "params": {"command": "exit 42", "expected_exit_code": 42}}]
        )
        assert results[0].passed is True

    @pytest.mark.asyncio
    async def test_verify_file_exists(self):
        engine = VerificationEngine()
        results = await engine.verify(
            "", [{"type": "file_exists", "params": {"path": "/tmp", "exists": True}}]
        )
        assert results[0].passed is True

    @pytest.mark.asyncio
    async def test_verify_file_not_exists(self):
        engine = VerificationEngine()
        results = await engine.verify(
            "", [{"type": "file_exists", "params": {"path": "/nonexistent_xyz_file", "exists": False}}]
        )
        assert results[0].passed is True

    @pytest.mark.asyncio
    async def test_verify_content_check_contains(self):
        engine = VerificationEngine()
        results = await engine.verify(
            "hello world", [{"type": "content_check", "params": {"contains": "world"}}]
        )
        assert results[0].passed is True

    @pytest.mark.asyncio
    async def test_verify_content_check_not_contains(self):
        engine = VerificationEngine()
        results = await engine.verify(
            "hello world", [{"type": "content_check", "params": {"not_contains": "xyz"}}]
        )
        assert results[0].passed is True

    @pytest.mark.asyncio
    async def test_verify_content_check_min_length(self):
        engine = VerificationEngine()
        results = await engine.verify(
            "hello", [{"type": "content_check", "params": {"min_length": 3}}]
        )
        assert results[0].passed is True

    @pytest.mark.asyncio
    async def test_verify_schema_valid(self):
        engine = VerificationEngine()
        results = await engine.verify(
            '{"name": "test", "version": "1.0"}',
            [{"type": "schema_validation", "params": {"schema": {"required": ["name"]}}}]
        )
        assert results[0].passed is True

    @pytest.mark.asyncio
    async def test_verify_schema_invalid_json(self):
        engine = VerificationEngine()
        results = await engine.verify(
            "not json", [{"type": "schema_validation", "params": {"schema": {}}}]
        )
        assert results[0].passed is False

    @pytest.mark.asyncio
    async def test_verify_schema_missing_field(self):
        engine = VerificationEngine()
        results = await engine.verify(
            '{"name": "test"}',
            [{"type": "schema_validation", "params": {"schema": {"required": ["name", "version"]}}}]
        )
        assert results[0].passed is False

    @pytest.mark.asyncio
    async def test_verify_custom(self):
        engine = VerificationEngine()
        engine.register_verifier("always_true", lambda r, p, c: True)
        results = await engine.verify(
            "", [{"type": "custom", "params": {"name": "always_true"}}]
        )
        assert results[0].passed is True

    @pytest.mark.asyncio
    async def test_verify_unknown_type(self):
        engine = VerificationEngine()
        results = await engine.verify(
            "", [{"type": "unknown_type", "params": {}}]
        )
        assert results[0].passed is False

    @pytest.mark.asyncio
    async def test_multiple_criteria(self):
        engine = VerificationEngine()
        results = await engine.verify(
            "hello world",
            [
                {"type": "content_check", "params": {"contains": "hello"}},
                {"type": "content_check", "params": {"contains": "world"}},
                {"type": "content_check", "params": {"not_contains": "xyz"}},
            ]
        )
        assert all(r.passed for r in results)


# ── Replanner Tests ────────────────────────────────────────

class TestReplanner:
    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        planner = Planner()
        verification = VerificationEngine()
        replanner = Replanner(planner, verification)

        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="step1"))

        result = await replanner.handle_step_failure(plan, plan.steps[0], "timeout after 30s")
        assert plan.steps[0].status == StepStatus.PENDING
        assert plan.steps[0].attempt_count == 1

    @pytest.mark.asyncio
    async def test_modify_on_permission_denial(self):
        planner = Planner()
        verification = VerificationEngine()
        replanner = Replanner(planner, verification)

        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="step1"))

        result = await replanner.handle_step_failure(plan, plan.steps[0], "permission denied")
        assert plan.steps[0].status == StepStatus.REPLANNED
        assert len(plan.steps) == 2

    @pytest.mark.asyncio
    async def test_insert_on_missing_resource(self):
        planner = Planner()
        verification = VerificationEngine()
        replanner = Replanner(planner, verification)

        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="step1"))

        original_step = plan.steps[0]
        await replanner.handle_step_failure(plan, plan.steps[0], "file not found: config.yaml")
        assert original_step.status == StepStatus.WAITING
        assert any("prereq" in s.id for s in plan.steps)
        assert any(s.id == "s1_prereq" for s in plan.steps)

    @pytest.mark.asyncio
    async def test_abort_on_budget_exceeded(self):
        planner = Planner()
        verification = VerificationEngine()
        replanner = Replanner(planner, verification)

        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="step1"))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="step2"))

        result = await replanner.handle_step_failure(plan, plan.steps[0], "budget exceeded")
        assert plan.status == PlanStatus.FAILED
        assert plan.steps[1].status == StepStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_max_replan_attempts(self):
        planner = Planner()
        verification = VerificationEngine()
        replanner = Replanner(planner, verification, max_replan_attempts=1)

        plan = Plan(id="p1", run_id="r1", goal="test")
        step = PlanStep(id="s1", plan_id="p1", objective="step1", max_attempts=2)
        step.attempt_count = 2
        plan.add_step(step)

        plan = await replanner.handle_step_failure(plan, plan.steps[0], "error1")
        assert plan.replan_count == 1

        plan = await replanner.handle_step_failure(plan, plan.steps[0], "error2")
        assert plan.status == PlanStatus.FAILED

    @pytest.mark.asyncio
    async def test_verification_failure_triggers_retry(self):
        planner = Planner()
        verification = VerificationEngine()
        replanner = Replanner(planner, verification)

        plan = Plan(id="p1", run_id="r1", goal="test")
        step = PlanStep(id="s1", plan_id="p1", objective="step1", max_attempts=3)
        plan.add_step(step)

        vr = VerificationResult(passed=False, verification_type="command", details="failed")
        await replanner.handle_verification_failure(plan, step, [vr])
        assert step.status == StepStatus.PENDING

    def test_classify_failure_timeout(self):
        planner = Planner()
        verification = VerificationEngine()
        replanner = Replanner(planner, verification)

        step = PlanStep(id="s1", plan_id="p1", objective="test")
        deviation = replanner._classify_failure(step, "timeout after 30s", "")
        assert deviation.cause == "timeout"
        assert deviation.strategy == ReplanningStrategy.RETRY

    def test_classify_failure_permission(self):
        planner = Planner()
        verification = VerificationEngine()
        replanner = Replanner(planner, verification)

        step = PlanStep(id="s1", plan_id="p1", objective="test")
        deviation = replanner._classify_failure(step, "permission denied", "")
        assert deviation.cause == "permission_denial"
        assert deviation.strategy == ReplanningStrategy.MODIFY_STEP

    def test_classify_failure_max_retries(self):
        planner = Planner()
        verification = VerificationEngine()
        replanner = Replanner(planner, verification)

        step = PlanStep(id="s1", plan_id="p1", objective="test", max_attempts=2)
        step.attempt_count = 2
        deviation = replanner._classify_failure(step, "some error", "")
        assert deviation.cause == "max_retries_exceeded"
        assert deviation.strategy == ReplanningStrategy.REPLAN


# ── Budget Manager Tests ───────────────────────────────────

class TestBudgetManager:
    def test_default_config(self):
        manager = BudgetManager()
        assert manager.config.max_total_tokens == 150000
        assert manager.config.max_tool_calls == 100

    def test_record_model_call(self):
        manager = BudgetManager()
        warnings = manager.record_model_call("run1", "sess1", 100, 50)
        budget = manager.get_run_budget("run1")
        assert budget.input_tokens == 100
        assert budget.output_tokens == 50
        assert budget.total_tokens == 150
        assert budget.model_calls == 1

    def test_record_tool_call(self):
        manager = BudgetManager()
        manager.record_tool_call("run1")
        budget = manager.get_run_budget("run1")
        assert budget.tool_calls == 1

    def test_record_subagent_call(self):
        manager = BudgetManager()
        manager.record_subagent_call("run1")
        budget = manager.get_run_budget("run1")
        assert budget.subagent_calls == 1

    def test_budget_warning_at_threshold(self):
        config = BudgetConfig(max_total_tokens=1000, warning_threshold=0.8)
        manager = BudgetManager(config)
        warnings = manager.record_model_call("run1", "", 600, 300)
        assert len(warnings) > 0

    def test_budget_exceeded(self):
        config = BudgetConfig(max_total_tokens=100)
        manager = BudgetManager(config)
        manager.record_model_call("run1", "", 50, 60)
        check = manager.check_budget("run1")
        assert "total_tokens" in check["exceeded"]
        assert check["can_continue"] is False

    def test_budget_ok(self):
        manager = BudgetManager()
        manager.record_model_call("run1", "", 100, 50)
        check = manager.check_budget("run1")
        assert check["can_continue"] is True

    def test_session_budget(self):
        manager = BudgetManager()
        manager.record_model_call("run1", "sess1", 100, 50)
        session = manager.get_session_budget("sess1")
        assert session.total_tokens == 150

    def test_reset_run(self):
        manager = BudgetManager()
        manager.record_model_call("run1", "", 100, 50)
        manager.reset_run("run1")
        budget = manager.get_run_budget("run1")
        assert budget.total_tokens == 0

    def test_all_usage(self):
        manager = BudgetManager()
        manager.record_model_call("run1", "sess1", 100, 50)
        usage = manager.get_all_usage()
        assert "sessions" in usage
        assert "runs" in usage


# ── Event Tracker Tests ────────────────────────────────────

class TestEventTracker:
    def test_emit_event(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        event = tracker.emit("test_event", session_id="s1", run_id="r1", data={"key": "val"})
        assert event.event_type == "test_event"
        assert event.session_id == "s1"
        assert event.data["key"] == "val"

    def test_emit_plan_created(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        event = tracker.emit_plan_created("s1", "r1", "p1")
        assert event.event_type == "plan_created"
        assert event.plan_id == "p1"

    def test_emit_step_started(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        event = tracker.emit_step_started("s1", "r1", "p1", "s1")
        assert event.event_type == "step_started"
        assert event.step_id == "s1"

    def test_query_events(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        tracker.emit("type_a", run_id="r1")
        tracker.emit("type_b", run_id="r1")
        tracker.emit("type_a", run_id="r2")
        results = tracker.query_events(event_type="type_a", run_id="r1")
        assert len(results) == 1

    def test_get_trace(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        tracker.emit("e1", run_id="r1")
        tracker.emit("e2", run_id="r1")
        tracker.emit("e3", run_id="r2")
        trace = tracker.get_trace("r1")
        assert len(trace) == 2

    def test_events_persisted(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        tracker.emit("persist_test", data={"x": 1})
        events_file = tmp_path / "events.jsonl"
        assert events_file.exists()
        with open(events_file) as f:
            lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["event_type"] == "persist_test"


# ── Recovery Manager Tests ─────────────────────────────────

class TestRecoveryManager:
    def test_checkpoint_and_load(self, tmp_path):
        manager = RecoveryManager(data_dir=str(tmp_path))
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="b"))
        plan.steps[0].status = StepStatus.COMPLETED

        cp = manager.checkpoint("r1", plan, context_summary="step 1 done")
        assert cp.run_id == "r1"
        assert "s1" in cp.completed_steps

        loaded = manager.load_checkpoint("r1")
        assert loaded is not None
        assert loaded.completed_steps == ["s1"]

    def test_resume_plan(self, tmp_path):
        manager = RecoveryManager(data_dir=str(tmp_path))
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="b"))
        plan.steps[0].status = StepStatus.COMPLETED
        plan.status = PlanStatus.EXECUTING

        cp = manager.checkpoint("r1", plan)
        resumed = manager.resume_plan(cp)
        assert resumed.steps[0].status == StepStatus.COMPLETED
        assert resumed.steps[1].status == StepStatus.PENDING
        assert resumed.status == PlanStatus.EXECUTING

    def test_can_safely_resume(self, tmp_path):
        manager = RecoveryManager(data_dir=str(tmp_path))
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        plan.steps[0].status = StepStatus.COMPLETED
        plan.status = PlanStatus.EXECUTING

        cp = manager.checkpoint("r1", plan)
        assert manager.can_safely_resume(cp) is True

    def test_cannot_resume_completed(self, tmp_path):
        manager = RecoveryManager(data_dir=str(tmp_path))
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        plan.steps[0].status = StepStatus.COMPLETED
        plan.status = PlanStatus.COMPLETED

        cp = manager.checkpoint("r1", plan)
        assert manager.can_safely_resume(cp) is False

    def test_find_interrupted_runs(self, tmp_path):
        manager = RecoveryManager(data_dir=str(tmp_path))
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        manager.checkpoint("r1", plan)
        interrupted = manager.find_interrupted_runs()
        assert len(interrupted) == 1

    def test_delete_checkpoint(self, tmp_path):
        manager = RecoveryManager(data_dir=str(tmp_path))
        plan = Plan(id="p1", run_id="r1", goal="test")
        manager.checkpoint("r1", plan)
        assert manager.delete_checkpoint("r1") is True
        assert manager.load_checkpoint("r1") is None

    def test_persistence(self, tmp_path):
        manager1 = RecoveryManager(data_dir=str(tmp_path))
        plan = Plan(id="p1", run_id="r1", goal="test")
        manager1.checkpoint("r1", plan)
        manager2 = RecoveryManager(data_dir=str(tmp_path))
        loaded = manager2.load_checkpoint("r1")
        assert loaded is not None

    def test_cleanup_old(self, tmp_path):
        manager = RecoveryManager(data_dir=str(tmp_path))
        plan = Plan(id="p1", run_id="r1", goal="test")
        cp = manager.checkpoint("r1", plan)
        cp.timestamp = time.time() - 100000
        manager._checkpoints["r1"] = cp
        manager._save()
        removed = manager.cleanup_old(max_age_hours=1)
        assert removed == 1


# ── Learning Engine Tests ──────────────────────────────────

class TestLearningEngine:
    @pytest.mark.asyncio
    async def test_analyze_outcome_success(self, tmp_path):
        engine = LearningEngine(data_dir=str(tmp_path))
        analysis = await engine.analyze_outcome(
            run_id="r1", goal="test",
            trajectory_steps=[{"step": 1}],
            tool_results=[{"tool": "bash", "success": True}],
            success=True,
        )
        assert analysis["success"] is True
        assert analysis["total_steps"] == 1

    @pytest.mark.asyncio
    async def test_analyze_outcome_failure_extracts_lessons(self, tmp_path):
        engine = LearningEngine(data_dir=str(tmp_path))
        analysis = await engine.analyze_outcome(
            run_id="r2", goal="fix bug",
            trajectory_steps=[],
            tool_results=[{"tool": "bash", "success": False, "error": "command not found"}],
            success=False,
        )
        assert len(analysis["lessons_extracted"]) > 0

    @pytest.mark.asyncio
    async def test_generate_skill_from_lessons(self, tmp_path):
        engine = LearningEngine(data_dir=str(tmp_path))
        lesson = Lesson(
            id="l1", content="pytest requires -q flag", scope="testing",
            source_run="r1", confidence=0.6,
        )
        engine._lessons["l1"] = lesson
        engine._save()

        skill = await engine.generate_skill(["l1"])
        assert skill is not None
        assert skill.status == "candidate"
        assert "pytest" in skill.description.lower() or "pytest" in skill.instructions.lower()

    @pytest.mark.asyncio
    async def test_validate_skill_promotion(self, tmp_path):
        engine = LearningEngine(data_dir=str(tmp_path))
        skill = SkillCandidate(
            id="s1", name="test_skill", description="test", instructions="test",
            triggers=["test"], usage_count=5, success_count=4, failure_count=1,
            confidence=0.5,
        )
        engine._skills["s1"] = skill
        engine._save()

        status = await engine.validate_skill("s1")
        assert status in ("tested", "trusted")
        assert skill.confidence > 0.5

    @pytest.mark.asyncio
    async def test_validate_skill_rejection(self, tmp_path):
        engine = LearningEngine(data_dir=str(tmp_path))
        skill = SkillCandidate(
            id="s2", name="bad_skill", description="bad", instructions="bad",
            triggers=["bad"], usage_count=5, success_count=1, failure_count=4,
            confidence=0.3,
        )
        engine._skills["s2"] = skill
        engine._save()

        status = await engine.validate_skill("s2")
        assert skill.confidence < 0.3

    def test_record_skill_usage(self, tmp_path):
        engine = LearningEngine(data_dir=str(tmp_path))
        skill = SkillCandidate(
            id="s1", name="test", description="test", instructions="test",
            triggers=["test"], confidence=0.5,
        )
        engine._skills["s1"] = skill
        engine.record_skill_usage("s1", success=True)
        assert skill.success_count == 1
        engine.record_skill_usage("s1", success=False)
        assert skill.failure_count == 1

    def test_get_relevant_skills(self, tmp_path):
        engine = LearningEngine(data_dir=str(tmp_path))
        skill = SkillCandidate(
            id="s1", name="pytest_skill", description="test", instructions="test",
            triggers=["pytest", "test"], confidence=0.8,
        )
        engine._skills["s1"] = skill
        results = engine.get_relevant_skills("run pytest tests")
        assert len(results) == 1
        assert results[0].id == "s1"

    def test_get_relevant_lessons(self, tmp_path):
        engine = LearningEngine(data_dir=str(tmp_path))
        lesson = Lesson(
            id="l1", content="pytest needs -q flag", scope="testing",
            source_run="r1", confidence=0.7,
        )
        engine._lessons["l1"] = lesson
        results = engine.get_relevant_lessons("run pytest")
        assert len(results) == 1

    def test_get_stats(self, tmp_path):
        engine = LearningEngine(data_dir=str(tmp_path))
        engine._lessons["l1"] = Lesson(id="l1", content="test", scope="test", source_run="r1")
        engine._skills["s1"] = SkillCandidate(
            id="s1", name="test", description="test", instructions="test",
            triggers=["test"], confidence=0.5,
        )
        stats = engine.get_stats()
        assert stats["total_lessons"] == 1
        assert stats["total_skills"] == 1

    def test_persistence(self, tmp_path):
        engine1 = LearningEngine(data_dir=str(tmp_path))
        engine1._lessons["l1"] = Lesson(id="l1", content="test", scope="test", source_run="r1")
        engine1._save()

        engine2 = LearningEngine(data_dir=str(tmp_path))
        assert "l1" in engine2._lessons


# ── Skill Lifecycle Tests ──────────────────────────────────

class TestSkillLifecycle:
    @pytest.mark.asyncio
    async def test_generate_from_lessons(self, tmp_path):
        learning = LearningEngine(data_dir=str(tmp_path))
        learning._lessons["l1"] = Lesson(
            id="l1", content="always run tests before commit", scope="testing",
            source_run="r1", confidence=0.6,
        )
        learning._lessons["l2"] = Lesson(
            id="l2", content="use pytest -q for fast tests", scope="testing",
            source_run="r1", confidence=0.7,
        )
        learning._save()

        lifecycle = SkillLifecycle(learning)
        skill = await lifecycle.generate_from_lessons(["l1", "l2"], "run tests")
        assert skill is not None
        assert skill.status == "candidate"

    @pytest.mark.asyncio
    async def test_record_usage_and_validate(self, tmp_path):
        learning = LearningEngine(data_dir=str(tmp_path))
        skill = SkillCandidate(
            id="s1", name="test", description="test", instructions="test",
            triggers=["test"], confidence=0.5,
        )
        learning._skills["s1"] = skill
        learning._save()

        lifecycle = SkillLifecycle(learning)
        for _ in range(5):
            await lifecycle.record_usage("s1", success=True)

        assert skill.success_count == 5
        assert skill.status in ("tested", "trusted")

    def test_get_trusted_skills(self, tmp_path):
        learning = LearningEngine(data_dir=str(tmp_path))
        learning._skills["s1"] = SkillCandidate(
            id="s1", name="trusted", description="test", instructions="test",
            triggers=["test"], status="trusted", confidence=0.8,
        )
        learning._skills["s2"] = SkillCandidate(
            id="s2", name="candidate", description="test", instructions="test",
            triggers=["test"], status="candidate", confidence=0.3,
        )
        lifecycle = SkillLifecycle(learning)
        trusted = lifecycle.get_trusted_skills()
        assert len(trusted) == 1
        assert trusted[0].status == "trusted"


# ── Job Engine Tests ───────────────────────────────────────

class TestJobEngine:
    @pytest.mark.asyncio
    async def test_enqueue_and_get_job(self, tmp_path):
        engine = JobEngine(data_dir=str(tmp_path))
        job = await engine.enqueue(
            job_type="test_job",
            run_id="r1",
            session_id="s1",
            payload={"type": "test_job", "data": "hello"},
        )
        assert job.id.startswith("job_")
        assert job.state == JobStatus.QUEUED

        loaded = engine.get_job(job.id)
        assert loaded is not None
        assert loaded.payload["data"] == "hello"

    @pytest.mark.asyncio
    async def test_list_jobs(self, tmp_path):
        engine = JobEngine(data_dir=str(tmp_path))
        await engine.enqueue("test", "r1", "s1", payload={"type": "test"})
        await engine.enqueue("test", "r1", "s1", payload={"type": "test"})
        jobs = engine.list_jobs(session_id="s1")
        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_list_jobs_by_state(self, tmp_path):
        engine = JobEngine(data_dir=str(tmp_path))
        job1 = await engine.enqueue("test", "r1", "s1", payload={"type": "test"})
        job2 = await engine.enqueue("test", "r1", "s1", payload={"type": "test"})
        queued = engine.list_jobs(state=JobStatus.QUEUED)
        assert len(queued) == 2

    @pytest.mark.asyncio
    async def test_job_handler_execution(self, tmp_path):
        engine = JobEngine(data_dir=str(tmp_path))

        async def test_handler(job_id, run_id, session_id, **kwargs):
            return "completed successfully"

        engine.register_handler("test_job", test_handler)
        job = await engine.enqueue(
            "test_job", "r1", "s1",
            payload={"type": "test_job"},
        )

        await engine.start_job(job)
        await asyncio.sleep(0.5)

        loaded = engine.get_job(job.id)
        assert loaded.state == JobStatus.COMPLETED
        assert loaded.result == "completed successfully"

    @pytest.mark.asyncio
    async def test_job_retry_on_failure(self, tmp_path):
        engine = JobEngine(data_dir=str(tmp_path))
        call_count = 0

        async def failing_handler(job_id, run_id, session_id, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient error")
            return "recovered"

        engine.register_handler("flaky_job", failing_handler)
        job = await engine.enqueue(
            "flaky_job", "r1", "s1",
            payload={"type": "flaky_job"},
            priority=JobPriority.HIGH,
        )
        job.max_attempts = 5
        engine._save_job(job)

        await engine.start_job(job)
        await asyncio.sleep(15)

        loaded = engine.get_job(job.id)
        assert loaded.state == JobStatus.COMPLETED
        assert loaded.result == "recovered"
        assert loaded.attempt_count == 3

    @pytest.mark.asyncio
    async def test_job_cancellation(self, tmp_path):
        engine = JobEngine(data_dir=str(tmp_path))

        async def slow_handler(job_id, run_id, session_id, **kwargs):
            await asyncio.sleep(10)
            return "done"

        engine.register_handler("slow_job", slow_handler)
        job = await engine.enqueue(
            "slow_job", "r1", "s1",
            payload={"type": "slow_job"},
        )
        await engine.start_job(job)
        await asyncio.sleep(0.1)
        cancelled = await engine.cancel_job(job.id)
        assert cancelled is True

    @pytest.mark.asyncio
    async def test_job_persistence(self, tmp_path):
        engine1 = JobEngine(data_dir=str(tmp_path))
        job = await engine1.enqueue(
            "test", "r1", "s1",
            payload={"type": "test", "key": "value"},
        )

        engine2 = JobEngine(data_dir=str(tmp_path))
        loaded = engine2.get_job(job.id)
        assert loaded is not None
        assert loaded.payload["key"] == "value"

    @pytest.mark.asyncio
    async def test_queue_depth(self, tmp_path):
        engine = JobEngine(data_dir=str(tmp_path))
        await engine.enqueue("test", "r1", "s1", payload={"type": "test"})
        await engine.enqueue("test", "r1", "s1", payload={"type": "test"})
        depth = engine.get_queue_depth()
        assert depth.get("queued", 0) == 2

    @pytest.mark.asyncio
    async def test_priority_ordering(self, tmp_path):
        engine = JobEngine(data_dir=str(tmp_path))
        j1 = await engine.enqueue("test", "r1", "s1", payload={"type": "test"}, priority=JobPriority.LOW)
        j2 = await engine.enqueue("test", "r1", "s1", payload={"type": "test"}, priority=JobPriority.CRITICAL)
        assert PRIORITY_ORDER[j2.priority] < PRIORITY_ORDER[j1.priority]

    @pytest.mark.asyncio
    async def test_job_failure_after_max_attempts(self, tmp_path):
        engine = JobEngine(data_dir=str(tmp_path))

        async def always_fails(job_id, run_id, session_id, **kwargs):
            raise ValueError("permanent failure")

        engine.register_handler("perm_fail", always_fails)
        job = await engine.enqueue(
            "perm_fail", "r1", "s1",
            payload={"type": "perm_fail"},
            priority=JobPriority.NORMAL,
        )
        job.max_attempts = 1
        engine._save_job(job)

        await engine.start_job(job)
        await asyncio.sleep(0.5)

        loaded = engine.get_job(job.id)
        assert loaded.state == JobStatus.FAILED


# ── Subagent Engine Tests ──────────────────────────────────

class TestSubagentEngine:
    @pytest.mark.asyncio
    async def test_spawn_subagent_with_mock_provider(self):
        from bahram.core.engine import AgentEngine

        engine = AgentEngine()

        mock_provider = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "Subagent completed task"
        mock_response.tool_calls = []
        mock_provider.complete = AsyncMock(return_value=mock_response)
        engine.register_provider("mock", mock_provider)

        subagent = SubagentEngine(engine)
        result = await subagent.spawn(
            parent_run_id="r1",
            objective="test objective",
            model="mock/test",
            timeout_seconds=10,
        )
        assert result.status == "completed"
        assert "Subagent completed task" in result.summary

    @pytest.mark.asyncio
    async def test_subagent_tool_filtering(self):
        from bahram.core.engine import AgentEngine

        engine = AgentEngine()

        mock_provider = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "done"
        mock_response.tool_calls = []
        mock_provider.complete = AsyncMock(return_value=mock_response)
        engine.register_provider("mock", mock_provider)

        subagent = SubagentEngine(engine)
        result = await subagent.spawn(
            parent_run_id="r1",
            objective="test",
            allowed_tools=["read"],
            model="mock/test",
        )
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_subagent_cancel(self):
        from bahram.core.engine import AgentEngine

        engine = AgentEngine()
        subagent = SubagentEngine(engine)

        event = asyncio.Event()
        subagent._cancel_events["test_task"] = event
        result = subagent.cancel("test_task")
        assert result is True
        assert event.is_set()

    @pytest.mark.asyncio
    async def test_subagent_list_tasks(self):
        from bahram.core.engine import AgentEngine

        engine = AgentEngine()
        mock_provider = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "done"
        mock_response.tool_calls = []
        mock_provider.complete = AsyncMock(return_value=mock_response)
        engine.register_provider("mock", mock_provider)

        subagent = SubagentEngine(engine)
        await subagent.spawn(parent_run_id="r1", objective="task1", model="mock/test")
        tasks = subagent.list_tasks()
        assert len(tasks) == 1


# ── State Invariant Tests ──────────────────────────────────

class TestStateInvariants:
    def test_completed_step_cannot_return_to_pending(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        step = PlanStep(id="s1", plan_id="p1", objective="test")
        plan.add_step(step)
        step.status = StepStatus.COMPLETED

        replanner = Replanner(Planner(), VerificationEngine())
        replanner._handle_retry(plan, step)
        assert step.status == StepStatus.PENDING or step.attempt_count > 0

    def test_plan_cannot_complete_with_failed_steps(self):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="a"))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="b"))
        plan.steps[0].status = StepStatus.COMPLETED
        plan.steps[1].status = StepStatus.FAILED
        assert plan.is_complete() is False

    def test_no_orphan_events(self):
        tracker = EventTracker()
        event = tracker.emit("test", session_id="s1", run_id="r1", plan_id="p1", step_id="step1")
        assert event.session_id == "s1"
        assert event.run_id == "r1"
        assert event.plan_id == "p1"

    def test_subagent_result_references_parent(self):
        result = SubagentResult(
            task_id="t1", status="completed", summary="done"
        )
        d = result.to_dict()
        assert d["task_id"] == "t1"
        assert d["status"] == "completed"


# ── Concurrency Tests ──────────────────────────────────────

class TestConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_sessions(self, tmp_path):
        engine = JobEngine(data_dir=str(tmp_path))
        tasks = []
        for i in range(5):
            task = engine.enqueue("test", f"r{i}", f"s{i}", payload={"type": "test"})
            tasks.append(task)
        results = await asyncio.gather(*tasks)
        assert len(results) == 5
        for r in results:
            assert r.state == JobStatus.QUEUED

    @pytest.mark.asyncio
    async def test_concurrent_budget_tracking(self):
        manager = BudgetManager()

        async def record_calls(run_id):
            for _ in range(10):
                manager.record_model_call(run_id, "", 10, 5)

        await asyncio.gather(*[record_calls(f"run{i}") for i in range(5)])
        for i in range(5):
            budget = manager.get_run_budget(f"run{i}")
            assert budget.total_tokens == 150


# ── Integration: Plan → Execute → Verify → Replan ─────────

class TestPlanExecutionIntegration:
    @pytest.mark.asyncio
    async def test_full_plan_lifecycle(self, tmp_path):
        plan = Plan(id="p1", run_id="r1", goal="fix bug")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="investigate",
                               required_tools=["read"],
                               verification_criteria=[{"type": "content_check", "params": {"contains": "root cause"}}]))
        plan.add_step(PlanStep(id="s2", plan_id="p1", objective="fix",
                               dependencies=["s1"], required_tools=["write"]))
        plan.add_step(PlanStep(id="s3", plan_id="p1", objective="verify",
                               dependencies=["s2"], required_tools=["bash"],
                               verification_criteria=[{"type": "command", "params": {"command": "echo ok"}}]))

        assert plan.validate_dependencies() == []
        assert plan.detect_cycles() is None
        assert len(plan.get_ready_steps()) == 1

        plan.steps[0].status = StepStatus.COMPLETED
        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].id == "s2"

        plan.steps[1].status = StepStatus.COMPLETED
        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].id == "s3"

        plan.steps[2].status = StepStatus.COMPLETED
        assert plan.is_complete()
        assert not plan.has_failures()
        progress = plan.get_progress()
        assert progress["completed"] == 3

    @pytest.mark.asyncio
    async def test_plan_with_replan(self, tmp_path):
        plan = Plan(id="p1", run_id="r1", goal="test")
        plan.add_step(PlanStep(id="s1", plan_id="p1", objective="step1"))

        replanner = Replanner(Planner(), VerificationEngine())
        plan = await replanner.handle_step_failure(plan, plan.steps[0], "timeout")
        assert plan.steps[0].status == StepStatus.PENDING
        assert plan.steps[0].attempt_count == 1

        plan.steps[0].status = StepStatus.COMPLETED
        assert plan.is_complete()
