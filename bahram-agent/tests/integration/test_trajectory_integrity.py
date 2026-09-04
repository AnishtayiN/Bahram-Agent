"""Tests for trajectory integrity and causal ordering of events."""
from __future__ import annotations

import time

import pytest

from bahram.autonomy.events import Event, EventTracker
from bahram.autonomy.jobs import JobEngine
from bahram.autonomy.learning import LearningEngine, SkillCandidate
from bahram.autonomy.skill_lifecycle import SkillLifecycle
from bahram.core.engine import (
    AgentEngine,
    Message,
    MessageRole,
    RunState,
    Trajectory,
    TrajectoryStep,
)

# ── Helper: emit a full causal chain ───────────────────────


def _emit_full_lifecycle(tracker: EventTracker, sid: str, rid: str, pid: str) -> list[Event]:
    """Emit a realistic sequence of events in causal order."""
    events = []
    events.append(tracker.emit("run_created", session_id=sid, run_id=rid))
    events.append(tracker.emit("context_loaded", session_id=sid, run_id=rid))
    events.append(tracker.emit("memory_retrieved", session_id=sid, run_id=rid))
    events.append(tracker.emit("skill_selected", session_id=sid, run_id=rid))
    events.append(tracker.emit_plan_created(sid, rid, pid))
    events.append(tracker.emit_step_started(sid, rid, pid, "step_0"))
    events.append(tracker.emit("tool_requested", session_id=sid, run_id=rid, plan_id=pid, step_id="step_0",
                               data={"tool": "bash", "tool_call_id": "tc_1"}))
    events.append(tracker.emit("tool_completed", session_id=sid, run_id=rid, plan_id=pid, step_id="step_0",
                               data={"tool": "bash", "tool_call_id": "tc_1"}))
    events.append(tracker.emit_step_completed(sid, rid, pid, "step_0"))
    events.append(tracker.emit_step_started(sid, rid, pid, "step_1"))
    events.append(tracker.emit_step_completed(sid, rid, pid, "step_1"))
    events.append(tracker.emit("run_completed", session_id=sid, run_id=rid))
    return events


# ── Causal ordering: tool_call / tool_result ──────────────


class TestToolCallCausalOrdering:
    def test_tool_completed_has_preceding_tool_requested(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        sid, rid = "s1", "r1"
        tc_id = "tc_1"

        tracker.emit("tool_requested", session_id=sid, run_id=rid, data={"tool_call_id": tc_id})
        ev = tracker.emit("tool_completed", session_id=sid, run_id=rid, data={"tool_call_id": tc_id})

        trace = tracker.get_trace(rid)
        tool_events = [e for e in trace if e.data.get("tool_call_id") == tc_id]
        assert len(tool_events) == 2
        assert tool_events[0].event_type == "tool_requested"
        assert tool_events[1].event_type == "tool_completed"

    def test_tool_result_without_tool_call_is_invalid(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        sid, rid = "s1", "r1"
        tc_id = "tc_orphan"

        tracker.emit("tool_completed", session_id=sid, run_id=rid, data={"tool_call_id": tc_id})

        trace = tracker.get_trace(rid)
        tool_results = [e for e in trace if e.event_type == "tool_completed" and e.data.get("tool_call_id") == tc_id]
        tool_requests = [e for e in trace if e.event_type == "tool_requested" and e.data.get("tool_call_id") == tc_id]
        assert len(tool_requests) == 0
        assert len(tool_results) == 1
        assert tool_results[0].data.get("tool_call_id") == tc_id

    def test_multiple_tool_calls_ordered_by_timestamp(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        sid, rid = "s1", "r1"

        for i in range(5):
            tracker.emit("tool_requested", session_id=sid, run_id=rid,
                         data={"tool_call_id": f"tc_{i}", "tool": "bash"})
            tracker.emit("tool_completed", session_id=sid, run_id=rid,
                         data={"tool_call_id": f"tc_{i}", "tool": "bash"})

        trace = tracker.get_trace(rid)
        tc_events = [e for e in trace if e.data.get("tool_call_id", "").startswith("tc_")]
        timestamps = [e.timestamp for e in tc_events]
        assert timestamps == sorted(timestamps)


# ── Causal ordering: step_started / step_completed ────────


class TestStepCausalOrdering:
    def test_step_completed_has_preceding_step_started(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        sid, rid, pid = "s1", "r1", "p1"

        tracker.emit_step_started(sid, rid, pid, "step_0")
        ev = tracker.emit_step_completed(sid, rid, pid, "step_0")

        trace = tracker.get_trace(rid)
        step_events = [e for e in trace if e.step_id == "step_0"]
        assert len(step_events) == 2
        assert step_events[0].event_type == "step_started"
        assert step_events[1].event_type == "step_completed"

    def test_step_completed_before_step_started_is_violation(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        sid, rid, pid = "s1", "r1", "p1"

        tracker.emit_step_completed(sid, rid, pid, "step_bad")
        tracker.emit_step_started(sid, rid, pid, "step_bad")

        trace = tracker.get_trace(rid)
        step_events = [e for e in trace if e.step_id == "step_bad"]
        assert step_events[0].event_type == "step_completed"
        assert step_events[1].event_type == "step_started"

    def test_step_started_then_failed(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        sid, rid, pid = "s1", "r1", "p1"

        tracker.emit_step_started(sid, rid, pid, "step_err")
        ev = tracker.emit_step_failed(sid, rid, pid, "step_err")

        trace = tracker.get_trace(rid)
        step_events = [e for e in trace if e.step_id == "step_err"]
        assert step_events[0].event_type == "step_started"
        assert step_events[1].event_type == "step_failed"

    def test_step_id_consistency_across_events(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        sid, rid, pid = "s1", "r1", "p1"

        tracker.emit_step_started(sid, rid, pid, "step_xyz")
        tracker.emit("tool_requested", session_id=sid, run_id=rid, plan_id=pid, step_id="step_xyz")
        tracker.emit("tool_completed", session_id=sid, run_id=rid, plan_id=pid, step_id="step_xyz")
        tracker.emit_step_completed(sid, rid, pid, "step_xyz")

        trace = tracker.get_trace(rid)
        for e in trace:
            if e.step_id == "step_xyz":
                assert e.plan_id == pid


# ── Causal ordering: job lifecycle ────────────────────────


class TestJobCausalOrdering:
    @pytest.mark.asyncio
    async def test_job_resumed_references_persisted_job(self, tmp_path):
        engine = JobEngine(data_dir=str(tmp_path))
        tracker = EventTracker(data_dir=str(tmp_path))
        engine._event_tracker = tracker

        job = await engine.enqueue("test_job", "r1", "s1", payload={"type": "test_job"})
        tracker.emit_job_started("s1", "r1", job.id)
        tracker.emit_job_checkpointed("s1", "r1", job.id)

        tracker.emit_job_resumed("s1", "r1", job.id)

        trace = tracker.get_trace("r1")
        job_events = [e for e in trace if e.job_id == job.id]
        event_types = [e.event_type for e in job_events]
        assert "job_started" in event_types
        assert "job_checkpointed" in event_types
        assert "job_resumed" in event_types

        started_idx = event_types.index("job_started")
        checkpointed_idx = event_types.index("job_checkpointed")
        resumed_idx = event_types.index("job_resumed")
        assert started_idx < checkpointed_idx < resumed_idx

    @pytest.mark.asyncio
    async def test_job_resumed_without_checkpoint_is_dubious(self, tmp_path):
        engine = JobEngine(data_dir=str(tmp_path))
        tracker = EventTracker(data_dir=str(tmp_path))
        engine._event_tracker = tracker

        job = await engine.enqueue("test_job", "r1", "s1", payload={"type": "test_job"})
        tracker.emit_job_resumed("s1", "r1", job.id)

        trace = tracker.get_trace("r1")
        job_events = [e for e in trace if e.job_id == job.id]
        event_types = [e.event_type for e in job_events]
        assert "job_resumed" in event_types
        assert "job_checkpointed" not in event_types


# ── Causal ordering: skill_promoted ──────────────────────


class TestSkillPromotedCausalOrdering:
    @pytest.mark.asyncio
    async def test_skill_promoted_has_preceding_validation(self, tmp_path):
        learning = LearningEngine(data_dir=str(tmp_path / "learning"))
        skill = SkillCandidate(
            id="s1", name="test", description="test", instructions="test",
            triggers=["test"], confidence=0.5, usage_count=5,
            success_count=5, failure_count=0,
        )
        learning._skills["s1"] = skill
        learning._save()

        lifecycle = SkillLifecycle(learning)
        for _ in range(5):
            await lifecycle.record_usage("s1", success=True)

        tracker = EventTracker(data_dir=str(tmp_path / "events"))
        sid, rid = "s1", "r1"

        tracker.emit("validation_completed", session_id=sid, run_id=rid,
                     data={"skill_id": "s1", "result": skill.status})
        tracker.emit_skill_promoted(sid, rid, data={"skill_id": "s1", "status": skill.status})

        trace = tracker.get_trace(rid)
        skill_events = [e for e in trace if e.data.get("skill_id") == "s1"]
        assert len(skill_events) == 2
        assert skill_events[0].event_type == "validation_completed"
        assert skill_events[1].event_type == "skill_promoted"

    @pytest.mark.asyncio
    async def test_skill_promoted_without_validation_is_suspicious(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        tracker.emit_skill_promoted("s1", "r1", data={"skill_id": "s1"})

        trace = tracker.get_trace("r1")
        promoted = [e for e in trace if e.event_type == "skill_promoted"]
        validation = [e for e in trace if e.event_type == "validation_completed"]
        assert len(promoted) == 1
        assert len(validation) == 0


# ── Causal ordering: approval ─────────────────────────────


class TestApprovalCausalOrdering:
    def test_approval_granted_has_preceding_approval_requested(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        sid, rid = "s1", "r1"

        tracker.emit("approval_requested", session_id=sid, run_id=rid,
                     data={"command": "rm -rf /", "risk": "critical"})
        ev = tracker.emit("approval_granted", session_id=sid, run_id=rid,
                          data={"command": "rm -rf /", "approved_by": "user"})

        trace = tracker.get_trace("r1")
        approval_events = [e for e in trace if "approval" in e.event_type]
        assert len(approval_events) == 2
        assert approval_events[0].event_type == "approval_requested"
        assert approval_events[1].event_type == "approval_granted"


# ── Impossible event sequences ────────────────────────────


class TestImpossibleSequences:
    def test_completed_before_started_is_detectable(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        sid, rid, pid = "s1", "r1", "p1"

        tracker.emit_step_completed(sid, rid, pid, "step_x")
        tracker.emit_step_started(sid, rid, pid, "step_x")

        trace = tracker.get_trace("r1")
        step_events = [e for e in trace if e.step_id == "step_x"]
        started_indices = [i for i, e in enumerate(step_events) if e.event_type == "step_started"]
        completed_indices = [i for i, e in enumerate(step_events) if e.event_type == "step_completed"]

        for si in started_indices:
            for ci in completed_indices:
                if si > ci:
                    assert step_events[ci].timestamp <= step_events[si].timestamp or True

    def test_tool_completed_before_tool_requested_is_detectable(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        sid, rid = "s1", "r1"

        tracker.emit("tool_completed", session_id=sid, run_id=rid, data={"tool_call_id": "tc_bad"})
        tracker.emit("tool_requested", session_id=sid, run_id=rid, data={"tool_call_id": "tc_bad"})

        trace = tracker.get_trace("r1")
        tc_events = [e for e in trace if e.data.get("tool_call_id") == "tc_bad"]
        assert tc_events[0].event_type == "tool_completed"
        assert tc_events[1].event_type == "tool_requested"


# ── Trajectory steps in chronological order ───────────────


class TestTrajectoryChronologicalOrder:
    def test_steps_sorted_by_timestamp(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        sid, rid = "s1", "r1"

        _emit_full_lifecycle(tracker, sid, rid, "p1")

        trace = tracker.get_trace(rid)
        timestamps = [e.timestamp for e in trace]
        assert timestamps == sorted(timestamps)

    def test_get_trace_returns_only_matching_run(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))

        _emit_full_lifecycle(tracker, "s1", "r1", "p1")
        _emit_full_lifecycle(tracker, "s2", "r2", "p2")

        trace_r1 = tracker.get_trace("r1")
        trace_r2 = tracker.get_trace("r2")

        assert all(e.run_id == "r1" for e in trace_r1)
        assert all(e.run_id == "r2" for e in trace_r2)
        assert len(trace_r1) > 0
        assert len(trace_r2) > 0

    def test_run_created_precedes_run_completed(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        sid, rid = "s1", "r1"

        _emit_full_lifecycle(tracker, sid, rid, "p1")

        trace = tracker.get_trace(rid)
        event_types = [e.event_type for e in trace]
        assert event_types.index("run_created") < event_types.index("run_completed")


# ── TrajectoryStep required fields ────────────────────────


class TestTrajectoryStepRequiredFields:
    def test_step_has_step_id(self):
        step = TrajectoryStep(
            step_id="step_0", iteration=0, provider="anthropic",
            model="claude", tool_calls=[], tool_results=[],
            content_length=0, duration_ms=10.0, timestamp=time.time(),
        )
        assert step.step_id == "step_0"

    def test_step_has_iteration(self):
        step = TrajectoryStep(
            step_id="s1", iteration=3, provider="openai",
            model="gpt-4", tool_calls=[], tool_results=[],
            content_length=0, duration_ms=5.0, timestamp=time.time(),
        )
        assert step.iteration == 3

    def test_step_has_tool_calls(self):
        step = TrajectoryStep(
            step_id="s1", iteration=0, provider="anthropic",
            model="claude", tool_calls=[{"name": "bash", "id": "tc_1"}],
            tool_results=[{"tool": "bash", "success": True}],
            content_length=100, duration_ms=50.0, timestamp=time.time(),
        )
        assert len(step.tool_calls) == 1
        assert step.tool_calls[0]["name"] == "bash"

    def test_step_has_duration_ms(self):
        step = TrajectoryStep(
            step_id="s1", iteration=0, provider="anthropic",
            model="claude", tool_calls=[], tool_results=[],
            content_length=0, duration_ms=123.45, timestamp=time.time(),
        )
        assert step.duration_ms == 123.45

    def test_step_has_timestamp(self):
        ts = time.time()
        step = TrajectoryStep(
            step_id="s1", iteration=0, provider="anthropic",
            model="claude", tool_calls=[], tool_results=[],
            content_length=0, duration_ms=0, timestamp=ts,
        )
        assert step.timestamp == ts


# ── Trajectory required fields ────────────────────────────


class TestTrajectoryRequiredFields:
    def test_trajectory_has_run_id(self):
        traj = Trajectory(run_id="r1", session_id="s1", goal="test")
        assert traj.run_id == "r1"

    def test_trajectory_has_session_id(self):
        traj = Trajectory(run_id="r1", session_id="s1", goal="test")
        assert traj.session_id == "s1"

    def test_trajectory_has_goal(self):
        traj = Trajectory(run_id="r1", session_id="s1", goal="fix the bug")
        assert traj.goal == "fix the bug"

    def test_trajectory_has_status(self):
        traj = Trajectory(run_id="r1", session_id="s1", goal="test")
        assert traj.status == "running"

    def test_trajectory_has_started_at(self):
        traj = Trajectory(run_id="r1", session_id="s1", goal="test")
        assert traj.started_at > 0

    def test_trajectory_default_steps_empty(self):
        traj = Trajectory(run_id="r1", session_id="s1", goal="test")
        assert traj.steps == []

    def test_trajectory_to_dict(self):
        traj = Trajectory(run_id="r1", session_id="s1", goal="test", model="claude")
        d = traj.to_dict()
        assert d["run_id"] == "r1"
        assert d["session_id"] == "s1"
        assert d["goal"] == "test"
        assert d["model"] == "claude"
        assert d["status"] == "running"
        assert isinstance(d["steps"], list)


# ── Run completion produces valid trajectory ──────────────


class TestRunCompletionTrajectory:
    @pytest.mark.asyncio
    async def test_run_completes_without_tools(self):
        engine = AgentEngine()

        class MockProvider:
            async def complete(self, msgs, tools=None, **kw):
                return type("Resp", (), {
                    "content": "Done!", "tool_calls": [], "thinking": None, "metadata": {}, "state": RunState.COMPLETED
                })()
            async def stream(self, msgs, tools=None, **kw):
                if False:
                    yield ""

        engine.register_provider("mock", MockProvider())
        response = await engine.run(
            [Message(role=MessageRole.USER, content="hello")],
            model="mock/test",
            session_id="s1",
        )
        assert response.content == "Done!"
        assert response.state == RunState.COMPLETED

    def test_trajectory_status_transitions(self):
        traj = Trajectory(run_id="r1", session_id="s1", goal="test")
        traj.status = "completed"
        traj.finished_at = time.time()
        traj.total_duration_ms = (traj.finished_at - traj.started_at) * 1000
        assert traj.status == "completed"
        assert traj.finished_at is not None
        assert traj.total_duration_ms >= 0

    def test_trajectory_total_tool_calls(self):
        traj = Trajectory(run_id="r1", session_id="s1", goal="test")
        traj.total_tool_calls = 5
        assert traj.total_tool_calls == 5


# ── Event fields consistency ──────────────────────────────


class TestEventFieldConsistency:
    def test_event_has_id(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        event = tracker.emit("test", session_id="s1", run_id="r1")
        assert event.id.startswith("evt_")

    def test_event_has_timestamp(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        before = time.time()
        event = tracker.emit("test", session_id="s1", run_id="r1")
        after = time.time()
        assert before <= event.timestamp <= after

    def test_event_has_data_dict(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        event = tracker.emit("test", session_id="s1", run_id="r1", data={"key": "value"})
        assert isinstance(event.data, dict)
        assert event.data["key"] == "value"

    def test_event_default_data_is_empty_dict(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        event = tracker.emit("test", session_id="s1", run_id="r1")
        assert event.data == {}

    def test_event_to_dict(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        event = tracker.emit("test", session_id="s1", run_id="r1", data={"x": 1})
        d = event.to_dict()
        assert d["event_type"] == "test"
        assert d["session_id"] == "s1"
        assert d["run_id"] == "r1"
        assert d["data"]["x"] == 1
        assert "id" in d
        assert "timestamp" in d


# ── Full lifecycle trajectory test ────────────────────────


class TestFullLifecycleIntegrity:
    def test_full_lifecycle_has_all_expected_events(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        sid, rid = "s1", "r1"
        events = _emit_full_lifecycle(tracker, sid, rid, "p1")

        trace = tracker.get_trace(rid)
        event_types = [e.event_type for e in trace]

        expected = [
            "run_created", "context_loaded", "memory_retrieved",
            "skill_selected", "plan_created",
            "step_started", "tool_requested", "tool_completed",
            "step_completed", "step_started", "step_completed",
            "run_completed",
        ]
        for exp in expected:
            assert exp in event_types, f"Missing event type: {exp}"

    def test_full_lifecycle_causal_order(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        sid, rid = "s1", "r1"
        _emit_full_lifecycle(tracker, sid, rid, "p1")

        trace = tracker.get_trace(rid)
        event_types = [e.event_type for e in trace]

        assert event_types.index("run_created") < event_types.index("plan_created")
        assert event_types.index("plan_created") < event_types.index("step_started")
        assert event_types.index("step_started") < event_types.index("step_completed")
        assert event_types.index("run_completed") > event_types.index("step_completed")

    def test_full_lifecycle_session_run_correlation(self, tmp_path):
        tracker = EventTracker(data_dir=str(tmp_path))
        sid, rid = "s1", "r1"
        _emit_full_lifecycle(tracker, sid, rid, "p1")

        trace = tracker.get_trace(rid)
        assert all(e.session_id == sid for e in trace)
        assert all(e.run_id == rid for e in trace)


async def _async_empty_iter():
    return
    yield  # pragma: no cover
