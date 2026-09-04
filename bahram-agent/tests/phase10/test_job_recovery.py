"""Phase 10: Job recovery tests.

Tests that background jobs survive process restart and resume correctly.
"""
from __future__ import annotations

import asyncio
import tempfile

import pytest

from bahram.autonomy.jobs import JobEngine, JobPriority, JobStatus


class TestJobRecovery:
    """Verify job persistence and recovery after restart."""

    def setup_method(self):
        self._tmpdirs = []

    def teardown_method(self):
        import shutil
        for d in self._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def _make_engine(self, max_concurrent=3):
        tmpdir = tempfile.mkdtemp()
        self._tmpdirs.append(tmpdir)
        return JobEngine(data_dir=tmpdir, max_concurrent=max_concurrent)

    @pytest.mark.asyncio
    async def test_job_persists_to_database(self):
        """Enqueued job should be stored in SQLite."""
        engine = self._make_engine()

        job = await engine.enqueue(
            job_type="test_job",
            run_id="run_1",
            session_id="sess_1",
            payload={"action": "test"},
        )

        retrieved = engine.get_job(job.id)
        assert retrieved is not None
        assert retrieved.id == job.id
        assert retrieved.state == JobStatus.QUEUED
        assert retrieved.payload == {"action": "test"}

    @pytest.mark.asyncio
    async def test_job_survives_engine_restart(self):
        """Job state should persist when a new JobEngine is created with same data_dir."""
        tmpdir = tempfile.mkdtemp()
        self._tmpdirs.append(tmpdir)

        engine1 = JobEngine(data_dir=tmpdir)
        job = await engine1.enqueue(
            job_type="test_job",
            run_id="run_1",
            session_id="sess_1",
            payload={"action": "persist_test"},
        )

        engine2 = JobEngine(data_dir=tmpdir)
        retrieved = engine2.get_job(job.id)

        assert retrieved is not None
        assert retrieved.id == job.id
        assert retrieved.payload == {"action": "persist_test"}

    @pytest.mark.asyncio
    async def test_running_jobs_found_on_startup(self):
        """JobEngine should find unfinished jobs on initialization."""
        tmpdir = tempfile.mkdtemp()
        self._tmpdirs.append(tmpdir)

        engine1 = JobEngine(data_dir=tmpdir)
        job = await engine1.enqueue(
            job_type="test_job",
            run_id="run_1",
            session_id="sess_1",
        )

        conn = engine1._get_conn()
        conn.execute(
            "UPDATE jobs SET state = ? WHERE id = ?",
            (JobStatus.RUNNING.value, job.id),
        )
        conn.commit()

        engine2 = JobEngine(data_dir=tmpdir)
        running = engine2.list_jobs(state=JobStatus.RUNNING)
        assert len(running) >= 1
        assert any(j.id == job.id for j in running)

    @pytest.mark.asyncio
    async def test_job_retry_on_failure(self):
        """Failed jobs should be retried up to max_attempts."""
        engine = self._make_engine()

        call_count = 0

        async def failing_handler(job_id, run_id, session_id, **kwargs):
            nonlocal call_count
            call_count += 1
            raise ValueError(f"Attempt {call_count} failed")

        engine.register_handler("failing_job", failing_handler)

        job = await engine.enqueue(
            job_type="failing_job",
            run_id="run_1",
            session_id="sess_1",
            payload={"type": "failing_job"},
        )

        await engine.start_job(job)
        await asyncio.sleep(3)

        final_job = engine.get_job(job.id)
        assert final_job is not None
        assert final_job.state in (JobStatus.RETRYING, JobStatus.FAILED)
        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_job_cancellation(self):
        """Cancelled jobs should stop execution."""
        engine = self._make_engine()

        async def slow_handler(job_id, run_id, session_id, **kwargs):
            await asyncio.sleep(10)
            return "completed"

        engine.register_handler("slow_job", slow_handler)

        job = await engine.enqueue(
            job_type="slow_job",
            run_id="run_1",
            session_id="sess_1",
            payload={"type": "slow_job"},
        )

        await engine.start_job(job)
        await asyncio.sleep(0.2)

        cancelled = await engine.cancel_job(job.id)
        assert cancelled

        final_job = engine.get_job(job.id)
        assert final_job.state == JobStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_concurrent_job_limit(self):
        """Engine should enforce max concurrent jobs."""
        engine = self._make_engine(max_concurrent=2)

        async def blocking_handler(job_id, run_id, session_id, **kwargs):
            await asyncio.sleep(5)
            return "done"

        engine.register_handler("blocking_job", blocking_handler)

        jobs = []
        for i in range(4):
            job = await engine.enqueue(
                job_type="blocking_job",
                run_id=f"run_{i}",
                session_id="sess_1",
                payload={"type": "blocking_job"},
            )
            jobs.append(job)

        for job in jobs[:2]:
            await engine.start_job(job)

        assert engine._active_count <= 2

    @pytest.mark.asyncio
    async def test_job_priority_ordering(self):
        """High priority jobs should be listed before low priority."""
        engine = self._make_engine()

        low_job = await engine.enqueue(
            job_type="test", run_id="r1", session_id="s1",
            priority=JobPriority.LOW,
        )
        high_job = await engine.enqueue(
            job_type="test", run_id="r2", session_id="s1",
            priority=JobPriority.HIGH,
        )

        all_jobs = engine.list_jobs()
        high_idx = next(i for i, j in enumerate(all_jobs) if j.id == high_job.id)
        low_idx = next(i for i, j in enumerate(all_jobs) if j.id == low_job.id)

        assert high_idx < low_idx

    @pytest.mark.asyncio
    async def test_job_queue_depth(self):
        """Queue depth should accurately reflect job states."""
        engine = self._make_engine()

        for i in range(3):
            await engine.enqueue(
                job_type="test", run_id=f"run_{i}", session_id="s1",
            )

        depth = engine.get_queue_depth()
        assert depth.get("queued", 0) >= 3

    @pytest.mark.asyncio
    async def test_job_session_filtering(self):
        """Jobs should be filterable by session."""
        engine = self._make_engine()

        await engine.enqueue(job_type="test", run_id="r1", session_id="session_a")
        await engine.enqueue(job_type="test", run_id="r2", session_id="session_a")
        await engine.enqueue(job_type="test", run_id="r3", session_id="session_b")

        a_jobs = engine.list_jobs(session_id="session_a")
        b_jobs = engine.list_jobs(session_id="session_b")

        assert len(a_jobs) == 2
        assert len(b_jobs) == 1

    @pytest.mark.asyncio
    async def test_job_result_storage(self):
        """Completed jobs should store their result."""
        engine = self._make_engine()

        async def success_handler(job_id, run_id, session_id, **kwargs):
            return "success_result"

        engine.register_handler("success_job", success_handler)

        job = await engine.enqueue(
            job_type="success_job", run_id="r1", session_id="s1",
            payload={"type": "success_job"},
        )

        await engine.start_job(job)
        await asyncio.sleep(0.5)

        final_job = engine.get_job(job.id)
        assert final_job is not None
        assert final_job.state == JobStatus.COMPLETED
        assert final_job.result == "success_result"

    @pytest.mark.asyncio
    async def test_job_no_handler_fails(self):
        """Job with no registered handler should fail."""
        engine = self._make_engine()

        job = await engine.enqueue(
            job_type="unregistered_type",
            run_id="r1",
            session_id="s1",
        )

        await engine.start_job(job)
        await asyncio.sleep(0.2)

        final_job = engine.get_job(job.id)
        assert final_job.state == JobStatus.FAILED
        assert "No handler" in (final_job.error or "")

    @pytest.mark.asyncio
    async def test_job_to_dict(self):
        """Job to_dict should return all fields."""
        engine = self._make_engine()

        job = await engine.enqueue(
            job_type="test", run_id="r1", session_id="s1",
            payload={"key": "value"},
        )

        d = job.to_dict()
        assert "id" in d
        assert "state" in d
        assert "payload" in d
        assert d["payload"]["key"] == "value"
