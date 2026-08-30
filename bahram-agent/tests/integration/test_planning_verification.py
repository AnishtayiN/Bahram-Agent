"""Integration tests for planning, verification, and replanning as real behavioral components."""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
import uuid
from pathlib import Path

import pytest

from bahram.autonomy.plan import Plan, PlanStatus, PlanStep, StepStatus
from bahram.autonomy.recovery import RecoveryManager
from bahram.autonomy.verification import VerificationEngine, VerificationResult, VerificationType


def _make_plan(goal: str = "test goal", num_steps: int = 3) -> Plan:
    run_id = uuid.uuid4().hex[:12]
    plan = Plan(id=f"plan_{uuid.uuid4().hex[:8]}", run_id=run_id, goal=goal)
    for i in range(num_steps):
        step = PlanStep(
            id=f"step_{i+1}",
            plan_id=plan.id,
            objective=f"Objective for step {i+1}",
        )
        plan.add_step(step)
    return plan


def _step_to_running(step: PlanStep) -> None:
    step.status = StepStatus.RUNNING
    step.started_at = time.time()


def _step_to_completed(step: PlanStep, result: str = "done") -> None:
    step.status = StepStatus.COMPLETED
    step.result = result
    step.completed_at = time.time()


def _step_to_failed(step: PlanStep, reason: str = "failed") -> None:
    step.status = StepStatus.FAILED
    step.failure_reason = reason
    step.completed_at = time.time()


class TestRealPlanning:
    def test_plan_lifecycle_through_states(self) -> None:
        plan = _make_plan(num_steps=3)
        s1, s2, s3 = plan.steps

        assert plan.status == PlanStatus.CREATED
        assert len(plan.steps) == 3
        assert plan.is_complete() is False
        assert plan.has_failures() is False

        _step_to_running(s1)
        assert s1.status == StepStatus.RUNNING

        _step_to_completed(s1, result="step1 output")
        assert s1.status == StepStatus.COMPLETED
        assert s1.result == "step1 output"

        _step_to_running(s2)
        assert s2.status == StepStatus.RUNNING

        _step_to_failed(s2, reason="connection timeout")
        assert s2.status == StepStatus.FAILED
        assert s2.failure_reason == "connection timeout"

        assert plan.has_failures() is True

        progress = plan.get_progress()
        assert progress["total"] == 3
        assert progress["completed"] == 1
        assert progress["failed"] == 1
        assert progress["running"] == 0
        assert progress["pending"] == 1
        assert progress["progress_pct"] == pytest.approx(33.33, rel=0.01)

        assert plan.is_complete() is False

    def test_plan_completion_only_when_all_terminal(self) -> None:
        plan = _make_plan(num_steps=2)
        s1, s2 = plan.steps

        _step_to_running(s1)
        _step_to_completed(s1)
        assert plan.is_complete() is False

        _step_to_running(s2)
        _step_to_completed(s2)
        assert plan.is_complete() is True
        assert plan.has_failures() is False

        progress = plan.get_progress()
        assert progress["completed"] == 2
        assert progress["failed"] == 0
        assert progress["progress_pct"] == 100.0

    def test_plan_skipped_step_counts_as_complete(self) -> None:
        plan = _make_plan(num_steps=2)
        s1, s2 = plan.steps

        _step_to_running(s1)
        _step_to_completed(s1)
        s2.status = StepStatus.SKIPPED

        assert plan.is_complete() is True

    def test_plan_serialization_roundtrip(self) -> None:
        plan = _make_plan(num_steps=2)
        _step_to_running(plan.steps[0])
        _step_to_completed(plan.steps[0], result="ok")
        _step_to_failed(plan.steps[1], reason="nope")

        data = plan.to_dict()
        restored = Plan.from_dict(data)

        assert restored.id == plan.id
        assert restored.goal == plan.goal
        assert len(restored.steps) == 2
        assert restored.steps[0].status == StepStatus.COMPLETED
        assert restored.steps[0].result == "ok"
        assert restored.steps[1].status == StepStatus.FAILED
        assert restored.steps[1].failure_reason == "nope"

    def test_get_ready_steps_respects_dependencies(self) -> None:
        plan = _make_plan(num_steps=1)
        step1 = plan.steps[0]

        step2 = PlanStep(
            id="step_2",
            plan_id=plan.id,
            objective="depends on step1",
            dependencies=["step_1"],
        )
        plan.add_step(step2)

        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].id == "step_1"

        _step_to_running(step1)
        _step_to_completed(step1)

        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].id == "step_2"


class TestPlanPersistence:
    def test_checkpoint_and_restore_plan_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            recovery_dir = os.path.join(tmpdir, "recovery1")
            rm = RecoveryManager(data_dir=recovery_dir)

            plan = _make_plan(num_steps=3)
            _step_to_running(plan.steps[0])
            _step_to_completed(plan.steps[0], result="output_a")
            _step_to_running(plan.steps[1])
            _step_to_completed(plan.steps[1], result="output_b")

            run_id = plan.run_id
            cp = rm.checkpoint(run_id, plan, context_summary="halfway done")
            assert cp is not None
            assert cp.completed_steps == ["step_1", "step_2"]

            rm2 = RecoveryManager(data_dir=recovery_dir)
            cp2 = rm2.load_checkpoint(run_id)
            assert cp2 is not None
            assert cp2.completed_steps == ["step_1", "step_2"]
            assert cp2.context_summary == "halfway done"

            restored_plan = rm2.resume_plan(cp2)
            assert restored_plan.status == PlanStatus.EXECUTING
            assert restored_plan.steps[0].status == StepStatus.COMPLETED
            assert restored_plan.steps[0].result == "output_a"
            assert restored_plan.steps[1].status == StepStatus.COMPLETED
            assert restored_plan.steps[1].result == "output_b"
            assert restored_plan.steps[2].status == StepStatus.PENDING

    def test_resume_resets_running_steps_to_pending(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rm = RecoveryManager(data_dir=tmpdir)
            plan = _make_plan(num_steps=2)

            _step_to_running(plan.steps[0])
            _step_to_completed(plan.steps[0])
            _step_to_running(plan.steps[1])

            cp = rm.checkpoint(plan.run_id, plan)
            restored = rm.resume_plan(cp)

            assert restored.steps[0].status == StepStatus.COMPLETED
            assert restored.steps[1].status == StepStatus.PENDING
            assert restored.steps[1].attempt_count == 1

    def test_delete_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rm = RecoveryManager(data_dir=tmpdir)
            plan = _make_plan(num_steps=1)
            _step_to_running(plan.steps[0])
            _step_to_completed(plan.steps[0])

            rm.checkpoint(plan.run_id, plan)
            assert rm.load_checkpoint(plan.run_id) is not None

            rm.delete_checkpoint(plan.run_id)
            assert rm.load_checkpoint(plan.run_id) is None

    def test_cannot_safely_resume_completed_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rm = RecoveryManager(data_dir=tmpdir)
            plan = _make_plan(num_steps=1)
            _step_to_running(plan.steps[0])
            _step_to_completed(plan.steps[0])
            plan.status = PlanStatus.COMPLETED

            cp = rm.checkpoint(plan.run_id, plan)
            assert rm.can_safely_resume(cp) is False


class TestVerificationEngine:
    @pytest.fixture
    def engine(self) -> VerificationEngine:
        return VerificationEngine()

    @pytest.mark.asyncio
    async def test_content_check_contains(self, engine: VerificationEngine) -> None:
        results = await engine.verify(
            result="hello world",
            criteria=[{"type": "content_check", "params": {"contains": "world"}}],
        )
        assert len(results) == 1
        assert results[0].passed is True
        assert results[0].verification_type == VerificationType.CONTENT_CHECK

    @pytest.mark.asyncio
    async def test_content_check_not_contains(self, engine: VerificationEngine) -> None:
        results = await engine.verify(
            result="hello world",
            criteria=[{"type": "content_check", "params": {"not_contains": "xyz"}}],
        )
        assert len(results) == 1
        assert results[0].passed is True

    @pytest.mark.asyncio
    async def test_content_check_fails_on_missing(self, engine: VerificationEngine) -> None:
        results = await engine.verify(
            result="hello",
            criteria=[{"type": "content_check", "params": {"contains": "missing"}}],
        )
        assert results[0].passed is False

    @pytest.mark.asyncio
    async def test_command_verification_safe(self, engine: VerificationEngine) -> None:
        results = await engine.verify(
            result="",
            criteria=[{"type": "command", "params": {"command": "echo ok", "expected_exit_code": 0}}],
        )
        assert len(results) == 1
        assert results[0].passed is True
        assert results[0].evidence["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_command_verification_fails_on_bad_exit(self, engine: VerificationEngine) -> None:
        results = await engine.verify(
            result="",
            criteria=[{"type": "command", "params": {"command": "exit 1", "expected_exit_code": 0}}],
        )
        assert results[0].passed is False

    @pytest.mark.asyncio
    async def test_file_exists_verification(self, engine: VerificationEngine) -> None:
        with tempfile.NamedTemporaryFile() as f:
            results = await engine.verify(
                result="",
                criteria=[{"type": "file_exists", "params": {"path": f.name, "exists": True}}],
            )
            assert results[0].passed is True

    @pytest.mark.asyncio
    async def test_file_not_exists_verification(self, engine: VerificationEngine) -> None:
        results = await engine.verify(
            result="",
            criteria=[{"type": "file_exists", "params": {"path": "/nonexistent/path/xyz", "exists": False}}],
        )
        assert results[0].passed is True

    @pytest.mark.asyncio
    async def test_unknown_type_returns_failure(self, engine: VerificationEngine) -> None:
        results = await engine.verify(
            result="",
            criteria=[{"type": "bogus_type", "params": {}}],
        )
        assert results[0].passed is False
        assert "Unknown verification type" in results[0].details

    @pytest.mark.asyncio
    async def test_multiple_criteria_all_must_pass(self, engine: VerificationEngine) -> None:
        criteria = [
            {"type": "content_check", "params": {"contains": "hello"}},
            {"type": "content_check", "params": {"contains": "world"}},
        ]
        results = await engine.verify(result="hello world", criteria=criteria)
        assert all(r.passed for r in results)

        criteria_fail = [
            {"type": "content_check", "params": {"contains": "hello"}},
            {"type": "content_check", "params": {"contains": "missing"}},
        ]
        results_fail = await engine.verify(result="hello world", criteria=criteria_fail)
        assert results_fail[0].passed is True
        assert results_fail[1].passed is False

    @pytest.mark.asyncio
    async def test_custom_verifier_function(self, engine: VerificationEngine) -> None:
        def check_uppercase(result: str, params: dict, ctx: dict | None) -> bool:
            return result.isupper()

        engine.register_verifier("uppercase", check_uppercase)

        results = await engine.verify(
            result="HELLO",
            criteria=[{"type": "custom", "params": {"name": "uppercase"}}],
        )
        assert results[0].passed is True

        results_fail = await engine.verify(
            result="hello",
            criteria=[{"type": "custom", "params": {"name": "uppercase"}}],
        )
        assert results_fail[0].passed is False

    @pytest.mark.asyncio
    async def test_custom_async_verifier(self, engine: VerificationEngine) -> None:
        async def async_check(result: str, params: dict, ctx: dict | None) -> bool:
            return len(result) > 3

        engine.register_verifier("long_enough", async_check)

        results = await engine.verify(
            result="toolong",
            criteria=[{"type": "custom", "params": {"name": "long_enough"}}],
        )
        assert results[0].passed is True

    @pytest.mark.asyncio
    async def test_command_no_command_returns_failure(self, engine: VerificationEngine) -> None:
        results = await engine.verify(
            result="",
            criteria=[{"type": "command", "params": {}}],
        )
        assert results[0].passed is False
        assert "No command specified" in results[0].details


class TestReplanning:
    def test_replanning_transitions_plan_status(self) -> None:
        plan1 = _make_plan(num_steps=2)
        _step_to_running(plan1.steps[0])
        _step_to_completed(plan1.steps[0])
        _step_to_running(plan1.steps[1])
        _step_to_failed(plan1.steps[1], reason="stuck")

        assert plan1.has_failures() is True

        plan1.status = PlanStatus.REPLANNING
        assert plan1.status == PlanStatus.REPLANNING

        plan2 = _make_plan(goal="revised goal", num_steps=2)
        plan2.steps[0].objective = "retry step 1 differently"
        plan2.steps[1].objective = "new compensating step"

        assert plan2.steps[0].objective != plan1.steps[0].objective
        assert plan2.steps[1].objective != plan1.steps[1].objective

    def test_checkpoint_preserves_both_plans(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rm = RecoveryManager(data_dir=tmpdir)

            plan1 = _make_plan(goal="original", num_steps=2)
            _step_to_running(plan1.steps[0])
            _step_to_completed(plan1.steps[0])
            plan1.status = PlanStatus.REPLANNING

            plan2 = _make_plan(goal="revised", num_steps=3)

            rm.checkpoint(plan1.run_id, plan1, context_summary="plan1 failed")
            rm.checkpoint(plan2.run_id, plan2, context_summary="plan2 new")

            cp1 = rm.load_checkpoint(plan1.run_id)
            cp2 = rm.load_checkpoint(plan2.run_id)

            assert cp1 is not None
            assert cp2 is not None
            assert cp1.plan_state["goal"] == "original"
            assert cp2.plan_state["goal"] == "revised"
            assert cp1.plan_state["status"] == "replanning"
            assert cp2.plan_state["status"] == "created"
            assert len(cp2.plan_state["steps"]) == 3

    def test_replan_count_increments(self) -> None:
        plan = _make_plan()
        assert plan.replan_count == 0
        plan.replan_count += 1
        plan.status = PlanStatus.REPLANNING
        assert plan.replan_count == 1


class TestVerificationEvidence:
    @pytest.mark.asyncio
    async def test_result_has_required_fields(self) -> None:
        engine = VerificationEngine()
        results = await engine.verify(
            result="hello",
            criteria=[{"type": "content_check", "params": {"contains": "hello"}}],
        )
        vr = results[0]
        assert isinstance(vr.passed, bool)
        assert vr.verification_type == VerificationType.CONTENT_CHECK
        assert isinstance(vr.details, str)
        assert vr.duration_ms > 0
        assert isinstance(vr.evidence, dict)

    @pytest.mark.asyncio
    async def test_evidence_populated_on_pass(self) -> None:
        engine = VerificationEngine()
        results = await engine.verify(
            result="some output",
            criteria=[{"type": "content_check", "params": {"contains": "output"}}],
        )
        vr = results[0]
        assert vr.passed is True
        assert "result_length" in vr.evidence
        assert "preview" in vr.evidence
        assert vr.evidence["result_length"] == len("some output")

    @pytest.mark.asyncio
    async def test_duration_always_positive(self) -> None:
        engine = VerificationEngine()
        results = await engine.verify(
            result="x",
            criteria=[{"type": "content_check", "params": {"contains": "x"}}],
        )
        assert results[0].duration_ms >= 0

    @pytest.mark.asyncio
    async def test_command_evidence_contains_stdout(self) -> None:
        engine = VerificationEngine()
        results = await engine.verify(
            result="",
            criteria=[{"type": "command", "params": {"command": "echo test_output_123"}}],
        )
        vr = results[0]
        assert vr.passed is True
        assert "test_output_123" in vr.evidence["stdout"]

    def test_verification_result_to_dict(self) -> None:
        vr = VerificationResult(
            passed=True,
            verification_type="test",
            details="ok",
            duration_ms=1.5,
            evidence={"key": "val"},
        )
        d = vr.to_dict()
        assert d["passed"] is True
        assert d["verification_type"] == "test"
        assert d["duration_ms"] == 1.5
        assert d["evidence"]["key"] == "val"


class TestPlanStepDependencyResolution:
    def test_step_not_ready_until_dependency_completed(self) -> None:
        plan = _make_plan(num_steps=1)
        step1 = plan.steps[0]

        step2 = PlanStep(
            id="step_2",
            plan_id=plan.id,
            objective="depends on step1",
            dependencies=["step_1"],
        )
        plan.add_step(step2)

        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].id == "step_1"

        _step_to_running(step1)
        ready = plan.get_ready_steps()
        assert len(ready) == 0

        _step_to_completed(step1)
        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].id == "step_2"

    def test_chain_of_dependencies(self) -> None:
        plan = Plan(
            id="chain_plan",
            run_id="run_chain",
            goal="chain test",
        )
        for i in range(4):
            deps = [f"step_{i}"] if i > 0 else []
            plan.add_step(PlanStep(
                id=f"step_{i+1}",
                plan_id=plan.id,
                objective=f"step {i+1}",
                dependencies=deps,
            ))

        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].id == "step_1"

        _step_to_running(plan.steps[0])
        _step_to_completed(plan.steps[0])
        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].id == "step_2"

        _step_to_running(plan.steps[1])
        _step_to_completed(plan.steps[1])
        ready = plan.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].id == "step_3"

    def test_cycle_detection(self) -> None:
        plan = Plan(id="cyc", run_id="r1", goal="cycle")
        step_a = PlanStep(id="a", plan_id="cyc", objective="a", dependencies=["b"])
        step_b = PlanStep(id="b", plan_id="cyc", objective="b", dependencies=["c"])
        step_c = PlanStep(id="c", plan_id="cyc", objective="c", dependencies=["a"])
        plan.steps = [step_a, step_b, step_c]

        cycles = plan.detect_cycles()
        assert cycles is not None
        assert len(cycles) > 0

    def test_no_cycle_in_dag(self) -> None:
        plan = Plan(id="dag", run_id="r1", goal="dag")
        step_a = PlanStep(id="a", plan_id="dag", objective="a")
        step_b = PlanStep(id="b", plan_id="dag", objective="b", dependencies=["a"])
        step_c = PlanStep(id="c", plan_id="dag", objective="c", dependencies=["a", "b"])
        plan.steps = [step_a, step_b, step_c]

        cycles = plan.detect_cycles()
        assert cycles is None

    def test_validate_dependencies_catches_missing_refs(self) -> None:
        plan = Plan(id="val", run_id="r1", goal="val")
        step_a = PlanStep(id="a", plan_id="val", objective="a", dependencies=["nonexistent"])
        plan.steps = [step_a]

        errors = plan.validate_dependencies()
        assert len(errors) == 1
        assert "nonexistent" in errors[0]

    def test_insert_step_after_updates_dependencies(self) -> None:
        plan = _make_plan(num_steps=2)
        new_step = PlanStep(
            id="step_inserted",
            plan_id=plan.id,
            objective="inserted between 1 and 2",
        )
        result = plan.insert_step_after("step_1", new_step)
        assert result is True

        ids = [s.id for s in plan.steps]
        assert ids == ["step_1", "step_inserted", "step_2"]

        inserted = plan.get_step("step_inserted")
        assert "step_1" in inserted.dependencies

        step2 = plan.get_step("step_2")
        assert "step_inserted" not in step2.dependencies

    def test_remove_step_cleans_up_dependencies(self) -> None:
        plan = _make_plan(num_steps=1)
        step2 = PlanStep(
            id="step_2",
            plan_id=plan.id,
            objective="depends on step1",
            dependencies=["step_1"],
        )
        plan.add_step(step2)

        removed = plan.remove_step("step_1")
        assert removed is True
        assert plan.get_step("step_1") is None
        assert "step_1" not in plan.steps[0].dependencies

    def test_dependency_on_skipped_step_blocks_downstream(self) -> None:
        plan = _make_plan(num_steps=1)
        step2 = PlanStep(
            id="step_2",
            plan_id=plan.id,
            objective="depends on step1",
            dependencies=["step_1"],
        )
        plan.add_step(step2)

        plan.steps[0].status = StepStatus.SKIPPED

        ready = plan.get_ready_steps()
        assert len(ready) == 0
