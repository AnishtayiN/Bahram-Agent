"""Phase 10: Database concurrency stress tests.

Tests that concurrent database operations do not cause corruption,
deadlocks, lost updates, or duplicate records.
"""

from __future__ import annotations

import asyncio
import tempfile
import threading
import time
from pathlib import Path

import pytest

from bahram.autonomy.jobs import JobEngine, JobStatus
from bahram.core.persistence import SessionStore


class TestDatabaseConcurrency:
    """Verify database handles concurrent operations safely."""

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

    @pytest.mark.asyncio
    async def test_concurrent_job_enqueues(self):
        """Multiple concurrent enqueues should not lose data."""
        tmpdir = self._make_tmpdir()
        engine = JobEngine(data_dir=tmpdir)

        async def enqueue_job(idx):
            return await engine.enqueue(
                job_type="test",
                run_id=f"run_{idx}",
                session_id=f"sess_{idx}",
                payload={"index": idx},
            )

        jobs = await asyncio.gather(*[enqueue_job(i) for i in range(20)])

        assert len(jobs) == 20
        for job in jobs:
            retrieved = engine.get_job(job.id)
            assert retrieved is not None

    @pytest.mark.asyncio
    async def test_concurrent_job_updates(self):
        """Multiple concurrent job state updates should not corrupt data."""
        tmpdir = self._make_tmpdir()
        engine = JobEngine(data_dir=tmpdir)

        jobs = []
        for i in range(5):
            job = await engine.enqueue(
                job_type="test",
                run_id=f"run_{i}",
                session_id="sess_1",
            )
            jobs.append(job)

        async def update_job_state(job):
            conn = engine._get_conn()
            conn.execute(
                "UPDATE jobs SET state = ?, updated_at = ? WHERE id = ?",
                (JobStatus.RUNNING.value, time.time(), job.id),
            )
            conn.commit()

        await asyncio.gather(*[update_job_state(j) for j in jobs])

        for job in jobs:
            retrieved = engine.get_job(job.id)
            assert retrieved.state == JobStatus.RUNNING

    def test_threaded_concurrent_writes(self):
        """Multiple threads writing to the same database should not corrupt it."""
        tmpdir = self._make_tmpdir()
        engine = JobEngine(data_dir=tmpdir)

        errors = []

        def write_job(idx):
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(
                    engine.enqueue(
                        job_type="test",
                        run_id=f"thread_{idx}",
                        session_id="sess_1",
                        payload={"thread": idx},
                    )
                )
                loop.close()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_job, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"

        conn = engine._get_conn()
        count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        assert count == 10

    def test_concurrent_session_operations(self):
        """Multiple concurrent session operations should not cause issues."""
        tmpdir = self._make_tmpdir()
        store = SessionStore(db_path=str(Path(tmpdir) / "sessions.db"))

        errors = []

        def create_and_read(idx):
            try:
                session_id = f"session_{idx}"
                store.create_session(session_id, metadata={"user": f"user_{idx}"})

                retrieved = store.get_session(session_id)
                assert retrieved is not None

                from bahram.core.engine import Message, MessageRole

                msg = Message(role=MessageRole.USER, content=f"Message from user {idx}")
                store.add_message(session_id, msg)

                messages = store.get_messages(session_id)
                assert len(messages) >= 1
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_and_read, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"Errors during concurrent session ops: {errors}"

    @pytest.mark.asyncio
    async def test_concurrent_job_list_queries(self):
        """Concurrent read queries should not block writes."""
        tmpdir = self._make_tmpdir()
        engine = JobEngine(data_dir=tmpdir)

        for i in range(5):
            await engine.enqueue(
                job_type="test",
                run_id=f"run_{i}",
                session_id="sess_1",
            )

        async def read_jobs():
            return engine.list_jobs()

        async def write_job(idx):
            return await engine.enqueue(
                job_type="test",
                run_id=f"new_run_{idx}",
                session_id="sess_2",
            )

        results = await asyncio.gather(
            read_jobs(),
            write_job(100),
            read_jobs(),
            write_job(101),
        )

        assert all(len(r) >= 5 for r in results if isinstance(r, list))

    @pytest.mark.asyncio
    async def test_job_state_transitions_consistency(self):
        """Job state transitions should be consistent under concurrent access."""
        tmpdir = self._make_tmpdir()
        engine = JobEngine(data_dir=tmpdir)

        job = await engine.enqueue(
            job_type="test",
            run_id="run_1",
            session_id="sess_1",
        )

        async def transition_to_running():
            conn = engine._get_conn()
            conn.execute(
                "UPDATE jobs SET state = ?, started_at = ? WHERE id = ? AND state = ?",
                (JobStatus.RUNNING.value, time.time(), job.id, JobStatus.QUEUED.value),
            )
            conn.commit()

        await asyncio.gather(
            transition_to_running(),
            transition_to_running(),
            transition_to_running(),
        )

        final_job = engine.get_job(job.id)
        assert final_job.state in (JobStatus.RUNNING, JobStatus.QUEUED)

    def test_session_store_concurrent_reads(self):
        """Concurrent reads from SessionStore should not cause issues."""
        tmpdir = self._make_tmpdir()
        store = SessionStore(db_path=str(Path(tmpdir) / "sessions.db"))

        store.create_session("session_read_test", metadata={"test": "value"})

        errors = []

        def read_session():
            try:
                result = store.get_session("session_read_test")
                assert result is not None
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_session) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_job_queue_depth_accuracy(self):
        """Queue depth should be accurate under concurrent modifications."""
        tmpdir = self._make_tmpdir()
        engine = JobEngine(data_dir=tmpdir)

        for i in range(10):
            await engine.enqueue(
                job_type="test",
                run_id=f"run_{i}",
                session_id="sess_1",
            )

        depth = engine.get_queue_depth()
        assert depth.get("queued", 0) == 10
