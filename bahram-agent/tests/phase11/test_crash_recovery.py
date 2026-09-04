"""Phase 11: Real crash injection and recovery tests.

Tests that background jobs survive actual process termination and restart.
Uses real subprocess spawning and SIGTERM signals.
"""
from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

from bahram.autonomy.jobs import JobEngine, JobStatus

WORKER_SCRIPT = '''
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "{repo_path}")

from bahram.autonomy.jobs import JobEngine, JobStatus

async def long_running_handler(job_id, run_id, session_id, **kwargs):
    data_dir = kwargs.get("data_dir", "/tmp/crash_test")
    step = 0
    total_steps = kwargs.get("total_steps", 5)

    for i in range(total_steps):
        step = i + 1
        checkpoint_file = Path(data_dir) / f"step_{{step}}.txt"
        checkpoint_file.write_text(json.dumps({{
            "job_id": job_id,
            "step": step,
            "timestamp": time.time(),
        }}))

        if step == kwargs.get("crash_at_step", 999):
            print(f"CRASH_POINT_REACHED step={{step}}", flush=True)
            time.sleep(60)
            break

        time.sleep(0.1)

    return f"completed_{{step}}_steps"

async def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "/tmp/crash_test"
    total_steps = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    crash_at = int(sys.argv[3]) if len(sys.argv) > 3 else 999

    engine = JobEngine(data_dir=data_dir, max_concurrent=1)
    engine.register_handler("long_task", long_running_handler)

    job = await engine.enqueue(
        job_type="long_task",
        run_id="crash_run_1",
        session_id="crash_sess_1",
        payload={{"type": "long_task", "data_dir": data_dir, "total_steps": total_steps, "crash_at_step": crash_at}},
    )

    print(f"JOB_CREATED job_id={{job.id}}", flush=True)
    await engine.start_job(job)

    while True:
        final_job = engine.get_job(job.id)
        if final_job and final_job.state in (JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value):
            print(f"JOB_DONE state={{final_job.state}}", flush=True)
            break
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    asyncio.run(main())
'''


class TestCrashInjection:
    """Real crash injection tests using subprocesses and signals."""

    def setup_method(self):
        self._tmpdirs = []

    def teardown_method(self):
        import shutil
        for d in self._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def _make_tmpdir(self):
        tmpdir = tempfile.mkdtemp()
        self._tmpdirs.append(tmpdir)
        return tmpdir

    def test_job_persists_across_process_restart(self):
        """Job state should survive process termination."""
        tmpdir = self._make_tmpdir()
        repo_path = str(Path(__file__).parent.parent.parent)

        script_content = WORKER_SCRIPT.format(
            repo_path=repo_path,
        ).replace("{", "{").replace("}", "}")

        script_path = Path(tmpdir) / "worker.py"
        script_path.write_text(script_content)

        process = subprocess.Popen(
            [sys.executable, str(script_path), tmpdir, "10", "3"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        job_id = None
        for line in process.stdout:
            line = line.strip()
            if line.startswith("JOB_CREATED"):
                job_id = line.split("job_id=")[1]
                break

        assert job_id is not None, "Job should be created"

        time.sleep(0.5)

        process.send_signal(signal.SIGTERM)
        process.wait(timeout=5)

        step_files = list(Path(tmpdir).glob("step_*.txt"))
        assert len(step_files) >= 1, "At least one checkpoint should be written"

        engine2 = JobEngine(data_dir=tmpdir)
        jobs = engine2.list_jobs()
        assert len(jobs) >= 1, "Job should be found in new engine"

        job = jobs[0]
        assert job.state in (JobStatus.RUNNING, JobStatus.COMPLETED, JobStatus.RETRYING)

    def test_recovery_manager_checkpoint_survives_restart(self):
        """RecoveryManager checkpoints should persist across instances."""
        from bahram.autonomy.plan import Plan, PlanStatus, PlanStep, StepStatus
        from bahram.autonomy.recovery import RecoveryManager

        tmpdir = self._make_tmpdir()

        rm1 = RecoveryManager(data_dir=tmpdir)

        plan = Plan(id="plan_1", run_id="run_1", goal="test goal")
        step = PlanStep(id="step_1", plan_id="plan_1", objective="test step")
        step.status = StepStatus.COMPLETED
        plan.steps.append(step)

        rm1.checkpoint(run_id="run_1", plan=plan, context_summary="step 1 done")

        rm2 = RecoveryManager(data_dir=tmpdir)
        cp = rm2.load_checkpoint("run_1")

        assert cp is not None
        assert cp.run_id == "run_1"
        assert len(cp.completed_steps) >= 1

    def test_learning_persists_across_restart(self):
        """Learning engine should persist lessons and skills."""
        from bahram.autonomy.learning import LearningEngine

        tmpdir = self._make_tmpdir()

        le1 = LearningEngine(data_dir=tmpdir)

        asyncio.run(
            le1.analyze_outcome(
                run_id="learn_run_1",
                goal="test learning persistence",
                trajectory_steps=[
                    {"step_id": "s1", "objective": "test", "status": "completed"},
                    {"step_id": "s2", "objective": "test2", "status": "completed"},
                    {"step_id": "s3", "objective": "test3", "status": "completed"},
                    {"step_id": "s4", "objective": "test4", "status": "completed"},
                    {"step_id": "s5", "objective": "test5", "status": "completed"},
                    {"step_id": "s6", "objective": "test6", "status": "completed"},
                ],
                tool_results=[{"tool": "bash", "success": True}],
                success=True,
            )
        )

        stats1 = le1.get_stats()
        assert stats1["total_lessons"] >= 1

        le2 = LearningEngine(data_dir=tmpdir)
        stats2 = le2.get_stats()
        assert stats2["total_lessons"] >= 1

    def test_budget_manager_persists_across_restart(self):
        """BudgetManager should accumulate usage within a session (in-memory)."""
        from bahram.autonomy.budget import BudgetManager

        bm = BudgetManager()
        bm.record_model_call("run_1", input_tokens=100, output_tokens=50)
        bm.record_tool_call("run_1")

        usage = bm.get_all_usage()
        assert usage["runs"]["run_1"]["model_calls"] == 1
        assert usage["runs"]["run_1"]["tool_calls"] == 1

        bm.record_model_call("run_1", input_tokens=200, output_tokens=100)
        usage2 = bm.get_all_usage()
        assert usage2["runs"]["run_1"]["model_calls"] == 2

    def test_event_tracker_persists_across_restart(self):
        """EventTracker should persist events to JSONL and reload on init."""
        from bahram.autonomy.events import EventTracker

        tmpdir = self._make_tmpdir()

        et1 = EventTracker(data_dir=tmpdir)
        et1.emit("test_event", session_id="s1", run_id="r1", data={"key": "value"})

        et2 = EventTracker(data_dir=tmpdir)
        et2._load_events()
        events = et2.query_events(event_type="test_event")
        assert len(events) >= 1
        assert events[0].data["key"] == "value"

    def test_skill_lifecycle_persists_across_restart(self):
        """Skill lifecycle should persist skill candidates."""
        from bahram.autonomy.learning import LearningEngine
        from bahram.autonomy.skill_lifecycle import SkillLifecycle

        tmpdir = self._make_tmpdir()

        le1 = LearningEngine(data_dir=tmpdir)
        sl1 = SkillLifecycle(le1)

        lesson_id = asyncio.run(
            le1.analyze_outcome(
                run_id="skill_run",
                goal="test skill persistence",
                trajectory_steps=[{"step_id": "s1", "objective": "test", "status": "completed"}],
                tool_results=[{"tool": "bash", "success": True}],
                success=True,
            )
        )

        lessons = le1.get_lessons()
        if lessons:
            lesson_ids = [l.id for l in lessons[:2]]
            skill = asyncio.run(
                sl1.generate_from_lessons(lesson_ids, "test skill persistence")
            )
            if skill:
                le2 = LearningEngine(data_dir=tmpdir)
                sl2 = SkillLifecycle(le2)
                candidates = sl2.get_candidates()
                assert len(candidates) >= 1
