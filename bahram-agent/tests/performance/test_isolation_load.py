"""Load tests verifying session/user isolation under concurrent access.

Uses asyncio.gather for concurrency and real components with tmpdir isolation.
"""

from __future__ import annotations

import asyncio
import os
import statistics
import time

import pytest

from bahram.autonomy.budget import BudgetConfig, BudgetManager
from bahram.autonomy.events import EventTracker
from bahram.autonomy.jobs import JobEngine, JobPriority
from bahram.core.smart_context import SmartContextManager
from bahram.memory.semantic import SemanticMemory

NUM_CONCURRENT_USERS = 20
NUM_MEMORIES_PER_USER = 5
NUM_EVENTS_PER_SESSION = 10
NUM_MODEL_CALLS_PER_RUN = 10
NUM_SMART_CONTEXTS = 10
NUM_JOBS = 50


# ---------------------------------------------------------------------------
# 1. TestMemoryIsolationUnderLoad
# ---------------------------------------------------------------------------
class TestMemoryIsolationUnderLoad:
    @pytest.mark.asyncio
    async def test_concurrent_users_write_and_search_own_memories(self, tmp_path):
        user_prefix = "USERSECRET"

        async def user_work(user_idx: int):
            user_tag = f"{user_prefix}_{user_idx}"
            user_dir = str(tmp_path / f"user_{user_idx}")
            os.makedirs(user_dir, exist_ok=True)
            memory = SemanticMemory(data_dir=user_dir)
            for i in range(NUM_MEMORIES_PER_USER):
                content = f"Memory {i} belonging to {user_tag}"
                memory.add(content=content, source=user_tag)

            own_results = memory.search(query=user_tag, limit=50)
            assert len(own_results) >= NUM_MEMORIES_PER_USER, (
                f"User {user_idx}: expected >= {NUM_MEMORIES_PER_USER} own memories, got "
                f"{len(own_results)}"
            )
            memory.close()

        try:
            await asyncio.gather(*(user_work(i) for i in range(NUM_CONCURRENT_USERS)))
        finally:
            pass


# ---------------------------------------------------------------------------
# 2. TestBudgetIsolationUnderLoad
# ---------------------------------------------------------------------------
class TestBudgetIsolationUnderLoad:
    @pytest.mark.asyncio
    async def test_concurrent_runs_independent_budgets(self):
        config = BudgetConfig(max_total_tokens=100_000, max_cost_usd=10.0)
        bm = BudgetManager(config=config)

        async def run_work(run_idx: int):
            run_id = f"run_{run_idx}"
            session_id = f"sess_{run_idx}"
            for _ in range(NUM_MODEL_CALLS_PER_RUN):
                bm.record_model_call(
                    run_id=run_id,
                    session_id=session_id,
                    input_tokens=500,
                    output_tokens=300,
                )

        await asyncio.gather(*(run_work(i) for i in range(NUM_CONCURRENT_USERS)))

        # Each run must have exactly NUM_MODEL_CALLS_PER_RUN model calls
        for i in range(NUM_CONCURRENT_USERS):
            run_budget = bm.get_run_budget(f"run_{i}")
            assert run_budget.model_calls == NUM_MODEL_CALLS_PER_RUN, (
                f"Run {i}: expected {NUM_MODEL_CALLS_PER_RUN} calls, got {run_budget.model_calls}"
            )
            assert run_budget.total_tokens == NUM_MODEL_CALLS_PER_RUN * 800, (
                f"Run {i}: expected {NUM_MODEL_CALLS_PER_RUN * 800} tokens, got "
                f"{run_budget.total_tokens}"
            )

        # Session budgets must also match
        for i in range(NUM_CONCURRENT_USERS):
            session_budget = bm.get_session_budget(f"sess_{i}")
            assert session_budget.model_calls == NUM_MODEL_CALLS_PER_RUN
            assert session_budget.total_tokens == NUM_MODEL_CALLS_PER_RUN * 800

        # Cross-check: no run should see another run's counts
        all_run_calls = [
            bm.get_run_budget(f"run_{i}").model_calls for i in range(NUM_CONCURRENT_USERS)
        ]
        assert all(c == NUM_MODEL_CALLS_PER_RUN for c in all_run_calls)


# ---------------------------------------------------------------------------
# 3. TestEventIsolationUnderLoad
# ---------------------------------------------------------------------------
class TestEventIsolationUnderLoad:
    @pytest.mark.asyncio
    async def test_concurrent_sessions_event_isolation(self, tmp_path):
        import os as _os

        async def session_work(sess_idx: int):
            session_id = f"session_{sess_idx}"
            session_dir = str(tmp_path / f"events_{sess_idx}")
            _os.makedirs(session_dir, exist_ok=True)
            tracker = EventTracker(data_dir=session_dir)
            for i in range(NUM_EVENTS_PER_SESSION):
                tracker.emit(
                    event_type=f"test_event_{i}",
                    session_id=session_id,
                    run_id=f"run_{sess_idx}",
                    data={"seq": i},
                )
            own = tracker.query_events(session_id=session_id)
            assert len(own) == NUM_EVENTS_PER_SESSION, (
                f"Session {sess_idx}: expected {NUM_EVENTS_PER_SESSION} events, got {len(own)}"
            )
            for e in own:
                assert e.session_id == session_id

        await asyncio.gather(*(session_work(i) for i in range(NUM_CONCURRENT_USERS)))


# ---------------------------------------------------------------------------
# 4. TestSmartContextIsolationUnderLoad
# ---------------------------------------------------------------------------
class TestSmartContextIsolationUnderLoad:
    @pytest.mark.asyncio
    async def test_concurrent_smart_context_no_cross_contamination(self):
        contexts: list[SmartContextManager] = []
        for i in range(NUM_SMART_CONTEXTS):
            contexts.append(SmartContextManager(max_tokens=8192))

        async def ctx_work(idx: int):
            ctx = contexts[idx]
            marker = f"MARKER_{idx}_UNIQUE_CONTEXT"
            for i in range(5):
                ctx.add_context(content=f"{marker} chunk {i}", priority=i)
            ctx.add_history("user", f"User message from {idx}")
            ctx.add_history("assistant", f"Assistant reply from {idx}")

            msgs = ctx.build_context()
            # All messages must contain this instance's marker or be history
            for msg in msgs:
                content = msg.get("content", "")
                # Either it contains our marker, or it's a history message from this instance
                assert marker in content or f"from {idx}" in content, (
                    f"Cross-contamination detected in context {idx}: {content[:80]}"
                )

            # No other context's marker should appear
            for other_idx in range(NUM_SMART_CONTEXTS):
                if other_idx == idx:
                    continue
                other_marker = f"MARKER_{other_idx}_UNIQUE_CONTEXT"
                for msg in msgs:
                    content = msg.get("content", "")
                    assert other_marker not in content, (
                        f"Context {idx} contains other context {other_idx}'s marker"
                    )

        await asyncio.gather(*(ctx_work(i) for i in range(NUM_SMART_CONTEXTS)))

    @pytest.mark.asyncio
    async def test_build_messages_only_returns_own_context(self):
        """Verify build_messages() returns only this instance's context."""
        contexts = [SmartContextManager(max_tokens=8192) for _ in range(NUM_SMART_CONTEXTS)]

        async def verify(idx: int):
            ctx = contexts[idx]
            marker = f"CTX_{idx}_EXCLUSIVE"
            ctx.add_context(content=marker, priority=10)
            ctx.set_system_prompt(f"System prompt for {idx}")
            ctx.add_history("user", f"Hello from {idx}")

            msgs = ctx.build_messages()
            for msg in msgs:
                content = msg.content if hasattr(msg, "content") else msg.get("content", "")
                if (
                    marker not in content
                    and f"from {idx}" not in content
                    and str(idx) not in content
                ):
                    pytest.fail(f"Context {idx}: unexpected message content: {content[:100]}")

        await asyncio.gather(*(verify(i) for i in range(NUM_SMART_CONTEXTS)))


# ---------------------------------------------------------------------------
# 5. TestConcurrentJobCreation
# ---------------------------------------------------------------------------
class TestConcurrentJobCreation:
    @pytest.mark.asyncio
    async def test_concurrent_enqueue_unique_ids_and_persisted(self, tmp_path):
        engine = JobEngine(data_dir=str(tmp_path / "jobs"), max_concurrent=NUM_JOBS)

        async def create_job(job_idx: int):
            job = await engine.enqueue(
                job_type=f"job_type_{job_idx % 5}",
                run_id=f"run_{job_idx}",
                session_id=f"session_{job_idx % 10}",
                payload={"type": f"job_type_{job_idx % 5}", "index": job_idx},
                priority=JobPriority.NORMAL,
                user_id=f"user_{job_idx % 3}",
            )
            return job

        jobs = await asyncio.gather(*(create_job(i) for i in range(NUM_JOBS)))

        # All IDs must be unique
        ids = [j.id for j in jobs]
        assert len(set(ids)) == NUM_JOBS, (
            f"Duplicate job IDs found: {NUM_JOBS - len(set(ids))} collisions"
        )

        # All jobs must be persisted and retrievable
        for job in jobs:
            retrieved = engine.get_job(job.id)
            assert retrieved is not None, f"Job {job.id} not persisted"
            assert retrieved.id == job.id
            assert retrieved.session_id == job.session_id
            assert retrieved.run_id == job.run_id
            assert retrieved.user_id == job.user_id

        # Verify queue depth
        depth = engine.get_queue_depth()
        assert depth.get("queued", 0) == NUM_JOBS

    @pytest.mark.asyncio
    async def test_no_state_corruption_under_load(self, tmp_path):
        engine = JobEngine(data_dir=str(tmp_path / "jobs2"), max_concurrent=50)

        async def create_and_verify(idx: int):
            job = await engine.enqueue(
                job_type=f"work_{idx}",
                run_id=f"run_{idx}",
                session_id=f"sess_{idx}",
                payload={"type": f"work_{idx}", "idx": idx},
            )
            # Immediately verify no corruption
            fetched = engine.get_job(job.id)
            assert fetched is not None
            assert fetched.id == job.id
            assert fetched.state.value == "queued"
            return fetched

        all_jobs = await asyncio.gather(*(create_and_verify(i) for i in range(NUM_JOBS)))

        # Final integrity check
        all_ids = set()
        for j in all_jobs:
            fetched = engine.get_job(j.id)
            assert fetched is not None, f"Job {j.id} lost after concurrent creation"
            assert fetched.id not in all_ids, f"Duplicate: {fetched.id}"
            all_ids.add(fetched.id)

        assert len(all_ids) == NUM_JOBS


# ---------------------------------------------------------------------------
# 6. TestLoadSummary
# ---------------------------------------------------------------------------
class TestLoadSummary:
    @pytest.mark.asyncio
    async def test_mini_load_summary(self, tmp_path):
        """Run a mini load test measuring p50, p95, and error rate."""
        memory = SemanticMemory(data_dir=str(tmp_path / "mem"))
        event_tracker = EventTracker(data_dir=str(tmp_path / "evt"))
        bm = BudgetManager()
        contexts = [SmartContextManager(max_tokens=4096) for _ in range(10)]
        results: list[float] = []
        errors: list[str] = []

        async def mixed_operation(op_idx: int):
            start = time.monotonic()
            try:
                tag = f"load_user_{op_idx % 10}"

                # Memory write + search
                memory.add(content=f"Load test memory {op_idx}", source=tag)
                memory.search(query=tag)

                # Event emit + query
                event_tracker.emit(
                    event_type="load_test",
                    session_id=f"load_sess_{op_idx % 10}",
                    run_id=f"load_run_{op_idx % 10}",
                )
                event_tracker.query_events(session_id=f"load_sess_{op_idx % 10}")

                # Budget tracking
                bm.record_model_call(
                    run_id=f"load_run_{op_idx % 10}",
                    input_tokens=100,
                    output_tokens=50,
                )

                # Smart context
                ctx = contexts[op_idx % len(contexts)]
                ctx.add_context(content=f"Context from op {op_idx}", priority=op_idx)
                ctx.build_context()

                elapsed = time.monotonic() - start
                results.append(elapsed)
            except Exception as e:
                elapsed = time.monotonic() - start
                results.append(elapsed)
                errors.append(str(e))

        num_ops = 10
        await asyncio.gather(*(mixed_operation(i) for i in range(num_ops)))

        assert len(results) == num_ops

        p50 = statistics.median(results) * 1000
        p95 = sorted(results)[int(len(results) * 0.95)] * 1000
        error_rate = len(errors) / num_ops

        print(f"\nLoad test results ({num_ops} concurrent ops):")
        print(f"  p50:  {p50:.1f}ms")
        print(f"  p95:  {p95:.1f}ms")
        print(f"  errors: {len(errors)}/{num_ops} ({error_rate:.1%})")

        assert error_rate < 0.05, f"Error rate {error_rate:.1%} exceeds 5% threshold"
        assert len(results) == num_ops, "Not all operations completed"
