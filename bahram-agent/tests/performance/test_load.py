from __future__ import annotations

import asyncio
import os
import statistics
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest

from bahram.autonomy.budget import BudgetConfig, BudgetManager
from bahram.autonomy.events import EventTracker
from bahram.core.engine import (
    AgentEngine,
    AgentResponse,
    Message,
    MessageRole,
    ToolCall,
)
from bahram.memory.providers import LocalMemoryProvider, MemoryEntry


class MockProvider:
    def __init__(self, delay: float = 0.0, responses=None):
        self._delay = delay
        self._responses = list(responses or [AgentResponse(content="ok")])
        self.call_count = 0
        self.total_latency = 0.0
        self._lock = asyncio.Lock()

    async def complete(self, messages, tools=None, **kwargs):
        async with self._lock:
            self.call_count += 1
        start = time.time()
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        latency = time.time() - start
        self.total_latency += latency
        async with self._lock:
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
        await asyncio.sleep(0.001)
        return "ok"


@dataclass
class LoadTestResult:
    total_runs: int
    successful: int
    failed: int
    latencies: list[float] = field(default_factory=list)
    wall_clock: float = 0.0

    @property
    def error_rate(self) -> float:
        return self.failed / self.total_runs if self.total_runs else 0.0

    @property
    def throughput(self) -> float:
        return self.total_runs / self.wall_clock if self.wall_clock > 0 else 0.0

    @property
    def p50(self) -> float:
        return statistics.median(self.latencies) if self.latencies else 0.0

    @property
    def p95(self) -> float:
        if not self.latencies:
            return 0.0
        idx = int(len(self.latencies) * 0.95)
        return sorted(self.latencies)[min(idx, len(self.latencies) - 1)]

    @property
    def avg(self) -> float:
        return statistics.mean(self.latencies) if self.latencies else 0.0


def _make_engine_with_provider(delay: float = 0.01) -> tuple[AgentEngine, MockProvider]:
    engine = AgentEngine()
    provider = MockProvider(delay=delay)
    engine.providers["test"] = provider
    engine.register_tool("mock", MockTool())
    return engine, provider


async def _single_engine_run(
    engine: AgentEngine,
    run_id: str,
    model: str = "test/model",
) -> tuple[str, float, bool]:
    start = time.time()
    messages = [Message(role=MessageRole.USER, content=f"Task {run_id}")]
    try:
        resp = await engine.run(messages, model=model)
        elapsed = time.time() - start
        return run_id, elapsed, resp.state.value == "completed"
    except Exception:
        elapsed = time.time() - start
        return run_id, elapsed, False


class TestConcurrentEngineRuns:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("concurrency", [10, 25, 50])
    async def test_engine_concurrency(self, concurrency):
        engine, provider = _make_engine_with_provider(delay=0.005)

        start = time.time()
        tasks = [
            _single_engine_run(engine, f"run_{i}")
            for i in range(concurrency)
        ]
        results = await asyncio.gather(*tasks)
        wall_clock = time.time() - start

        result = LoadTestResult(
            total_runs=concurrency,
            successful=sum(1 for _, _, ok in results if ok),
            failed=sum(1 for _, _, ok in results if not ok),
            latencies=[lat for _, lat, _ in results],
            wall_clock=wall_clock,
        )

        assert result.error_rate == 0.0, f"Error rate {result.error_rate:.1%} exceeds 0%"
        assert result.p95 < 10.0, f"p95 latency {result.p95:.3f}s too high"
        assert result.throughput > 1.0, f"Throughput {result.throughput:.1f} runs/s too low"
        assert provider.call_count == concurrency

    @pytest.mark.asyncio
    async def test_concurrent_engine_runs_with_tool_calls(self):
        engine, provider = _make_engine_with_provider(delay=0.001)
        concurrency = 20

        async def _run_with_tool(run_id: str):
            messages = [Message(role=MessageRole.USER, content=f"Task {run_id}")]
            resp = await engine.run(messages, model="test/model")
            return resp

        start = time.time()
        tasks = [_run_with_tool(f"run_{i}") for i in range(concurrency)]
        results = await asyncio.gather(*tasks)
        wall_clock = time.time() - start

        all_completed = all(r.state.value == "completed" for r in results)
        assert all_completed, f"Some runs failed: {[r.state for r in results]}"
        assert wall_clock < 30.0, f"Wall clock {wall_clock:.1f}s too high for {concurrency} runs"

    @pytest.mark.asyncio
    async def test_throughput_scaling(self):
        results = {}
        for concurrency in [5, 15, 30]:
            engine, provider = _make_engine_with_provider(delay=0.002)
            start = time.time()
            tasks = [
                _single_engine_run(engine, f"run_{i}")
                for i in range(concurrency)
            ]
            run_results = await asyncio.gather(*tasks)
            wall_clock = time.time() - start

            latencies = [lat for _, lat, _ in run_results]
            results[concurrency] = {
                "wall_clock": wall_clock,
                "throughput": concurrency / wall_clock,
                "p50": statistics.median(latencies),
                "p95": sorted(latencies)[int(len(latencies) * 0.95)],
            }

        for c, r in results.items():
            assert r["throughput"] > 1.0, f"Throughput too low at concurrency={c}"


class TestConcurrentMemoryWrites:
    @pytest.mark.asyncio
    async def test_concurrent_memory_writes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = LocalMemoryProvider(data_dir=tmpdir)
            num_users = 25
            writes_per_user = 10
            total_expected = num_users * writes_per_user

            async def _user_writes(user_id: str, count: int):
                for i in range(count):
                    entry = MemoryEntry(
                        id=f"mem_{user_id}_{i}",
                        content=f"User {user_id} memory {i}",
                        metadata={"user_id": user_id, "index": i},
                        timestamp=time.time(),
                    )
                    await provider.add(entry)

            start = time.time()
            tasks = [
                _user_writes(f"user_{i}", writes_per_user)
                for i in range(num_users)
            ]
            await asyncio.gather(*tasks)
            wall_clock = time.time() - start

            count = await provider.count()
            assert count == total_expected, (
                f"Expected {total_expected} entries, got {count} "
                f"(lost {total_expected - count} writes)"
            )
            assert wall_clock < 15.0, f"Memory writes took {wall_clock:.1f}s"

    @pytest.mark.asyncio
    async def test_concurrent_memory_reads_and_writes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = LocalMemoryProvider(data_dir=tmpdir)

            for i in range(50):
                entry = MemoryEntry(
                    id=f"pre_{i}",
                    content=f"Pre-existing entry {i}",
                    metadata={"index": i},
                    timestamp=time.time(),
                )
                await provider.add(entry)

            async def _reader():
                return await provider.search("entry", limit=10)

            async def _writer(user_id: str):
                for i in range(5):
                    entry = MemoryEntry(
                        id=f"new_{user_id}_{i}",
                        content=f"New entry {user_id} {i}",
                        metadata={"user_id": user_id},
                        timestamp=time.time(),
                    )
                    await provider.add(entry)

            start = time.time()
            tasks = []
            for i in range(5):
                tasks.append(_reader())
                tasks.append(_writer(f"writer_{i}"))
            await asyncio.gather(*tasks)
            wall_clock = time.time() - start

            count = await provider.count()
            assert count >= 50, f"Pre-existing entries lost: only {count} remain"


class TestConcurrentBudgetTracking:
    @pytest.mark.asyncio
    async def test_no_lost_updates_budget(self):
        bm = BudgetManager(BudgetConfig(
            max_total_tokens=1_000_000,
            max_model_calls=10_000,
            max_tool_calls=10_000,
            max_cost_usd=1000.0,
        ))
        num_tasks = 50
        increments_per_task = 20

        async def _track_budget(task_id: str):
            run_id = f"run_{task_id}"
            for i in range(increments_per_task):
                bm.record_model_call(run_id, input_tokens=10, output_tokens=5)
                bm.record_tool_call(run_id)

        start = time.time()
        tasks = [_track_budget(f"t_{i}") for i in range(num_tasks)]
        await asyncio.gather(*tasks)
        wall_clock = time.time() - start

        total_model_calls = 0
        total_tool_calls = 0
        for i in range(num_tasks):
            run_id = f"run_t_{i}"
            budget = bm.get_run_budget(run_id)
            total_model_calls += budget.model_calls
            total_tool_calls += budget.tool_calls

        expected_model = num_tasks * increments_per_task
        expected_tools = num_tasks * increments_per_task
        assert total_model_calls == expected_model, (
            f"Lost model call updates: expected {expected_model}, got {total_model_calls}"
        )
        assert total_tool_calls == expected_tools, (
            f"Lost tool call updates: expected {expected_tools}, got {total_tool_calls}"
        )
        assert wall_clock < 10.0, f"Budget tracking took {wall_clock:.1f}s"

    @pytest.mark.asyncio
    async def test_shared_session_budget_concurrent(self):
        bm = BudgetManager(BudgetConfig(
            max_total_tokens=100_000,
            max_cost_usd=50.0,
            warning_threshold=0.5,
        ))
        session_id = "shared_session"
        num_tasks = 30
        tokens_per_call = 100

        async def _update_session():
            for _ in range(10):
                bm.record_model_call(
                    "run_tmp",
                    session_id=session_id,
                    input_tokens=tokens_per_call,
                    output_tokens=tokens_per_call,
                )

        start = time.time()
        tasks = [_update_session() for _ in range(num_tasks)]
        await asyncio.gather(*tasks)
        wall_clock = time.time() - start

        session_budget = bm.get_session_budget(session_id)
        expected_tokens = num_tasks * 10 * tokens_per_call * 2
        assert session_budget.total_tokens == expected_tokens, (
            f"Session token count wrong: expected {expected_tokens}, "
            f"got {session_budget.total_tokens}"
        )


class TestConcurrentEventEmission:
    @pytest.mark.asyncio
    async def test_no_lost_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = EventTracker(data_dir=tmpdir)
            num_tasks = 30
            events_per_task = 20
            total_expected = num_tasks * events_per_task

            async def _emit_events(task_id: str):
                for i in range(events_per_task):
                    tracker.emit(
                        "load_test_event",
                        session_id=f"sess_{task_id}",
                        run_id=f"run_{task_id}",
                        data={"task": task_id, "index": i},
                    )

            start = time.time()
            tasks = [_emit_events(f"t_{i}") for i in range(num_tasks)]
            await asyncio.gather(*tasks)
            wall_clock = time.time() - start

            all_events = tracker.query_events(event_type="load_test_event", limit=total_expected + 100)
            assert len(all_events) == total_expected, (
                f"Lost events: expected {total_expected}, got {len(all_events)}"
            )
            assert wall_clock < 15.0, f"Event emission took {wall_clock:.1f}s"

    @pytest.mark.asyncio
    async def test_concurrent_filtered_queries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = EventTracker(data_dir=tmpdir)

            for i in range(200):
                tracker.emit(
                    "query_test",
                    session_id=f"sess_{i % 5}",
                    run_id=f"run_{i}",
                    data={"index": i},
                )

            async def _query(session_id: str):
                return tracker.query_events(
                    event_type="query_test",
                    session_id=session_id,
                    limit=50,
                )

            start = time.time()
            tasks = [_query(f"sess_{i}") for i in range(5) for _ in range(10)]
            results = await asyncio.gather(*tasks)
            wall_clock = time.time() - start

            for result_list in results:
                for event in result_list:
                    assert event.event_type == "query_test"
            assert wall_clock < 5.0, f"Concurrent queries took {wall_clock:.1f}s"

    @pytest.mark.asyncio
    async def test_event_emission_with_mixed_types(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tracker = EventTracker(data_dir=tmpdir)
            event_types = ["plan_created", "step_started", "step_completed", "job_started"]

            async def _mixed_emitter(task_id: str):
                emitted = []
                for i, etype in enumerate(event_types):
                    event = tracker.emit(
                        etype,
                        session_id=f"sess_{task_id}",
                        run_id=f"run_{task_id}",
                        data={"task": task_id, "type_idx": i},
                    )
                    emitted.append(event)
                return emitted

            start = time.time()
            tasks = [_mixed_emitter(f"t_{i}") for i in range(20)]
            all_emitted = await asyncio.gather(*tasks)
            wall_clock = time.time() - start

            total_expected = 20 * len(event_types)
            all_events = tracker.query_events(limit=total_expected + 100)
            assert len(all_events) == total_expected


class TestSessionIsolationUnderLoad:
    @pytest.mark.asyncio
    async def test_session_data_isolation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            provider = LocalMemoryProvider(data_dir=tmpdir)
            user_a_id = "user_A"
            user_b_id = "user_B"
            num_entries = 20

            async def _write_user_data(user_id: str, prefix: str):
                for i in range(num_entries):
                    entry = MemoryEntry(
                        id=f"{user_id}_mem_{i}",
                        content=f"{prefix} data {i}",
                        metadata={"user_id": user_id, "secret": f"secret_{user_id}_{i}"},
                        timestamp=time.time(),
                    )
                    await provider.add(entry)

            await asyncio.gather(
                _write_user_data(user_a_id, "UserA"),
                _write_user_data(user_b_id, "UserB"),
            )

            results_a = await provider.search("UserA data", limit=100)
            results_b = await provider.search("UserB data", limit=100)

            for entry in results_a:
                assert entry.metadata.get("user_id") == user_a_id, (
                    f"User A got User B's data: {entry.id}"
                )
            for entry in results_b:
                assert entry.metadata.get("user_id") == user_b_id, (
                    f"User B got User A's data: {entry.id}"
                )

    @pytest.mark.asyncio
    async def test_engine_session_isolation(self):
        sessions = {}
        engines = {}

        for user in ["alice", "bob"]:
            engine, provider = _make_engine_with_provider(delay=0.001)
            engines[user] = engine
            sessions[user] = {
                "id": f"sess_{user}_{uuid.uuid4().hex[:6]}",
                "engine": engine,
                "provider": provider,
            }

        async def _run_in_session(user: str):
            sess = sessions[user]
            messages = [Message(
                role=MessageRole.USER,
                content=f"Hello, I am {user}. My secret is {user}_secret_123.",
            )]
            resp = await sess["engine"].run(messages, model="test/model")
            return user, resp.content, sess["id"]

        results = await asyncio.gather(*[_run_in_session(u) for u in ["alice", "bob"]])

        responses = {user: content for user, content, _ in results}
        assert "alice" in responses
        assert "bob" in responses

        alice_sid = next(sid for u, _, sid in results if u == "alice")
        bob_sid = next(sid for u, _, sid in results if u == "bob")
        assert alice_sid != bob_sid

    @pytest.mark.asyncio
    async def test_concurrent_budget_isolation(self):
        bm = BudgetManager(BudgetConfig(
            max_total_tokens=1_000_000,
            max_model_calls=10_000,
            max_tool_calls=10_000,
            max_cost_usd=1000.0,
        ))

        user_a_runs = [f"run_a_{i}" for i in range(10)]
        user_b_runs = [f"run_b_{i}" for i in range(10)]

        async def _track_user_runs(runs: list[str], user_label: str):
            for run_id in runs:
                for _ in range(5):
                    bm.record_model_call(run_id, input_tokens=100, output_tokens=50)
                    bm.record_tool_call(run_id)

        await asyncio.gather(
            _track_user_runs(user_a_runs, "A"),
            _track_user_runs(user_b_runs, "B"),
        )

        for run_id in user_a_runs:
            budget = bm.get_run_budget(run_id)
            assert budget.model_calls == 5, (
                f"User A run {run_id}: expected 5 model calls, got {budget.model_calls}"
            )
            assert budget.tool_calls == 5

        for run_id in user_b_runs:
            budget = bm.get_run_budget(run_id)
            assert budget.model_calls == 5, (
                f"User B run {run_id}: expected 5 model calls, got {budget.model_calls}"
            )
            assert budget.tool_calls == 5


class TestDatabaseContention:
    @pytest.mark.asyncio
    async def test_concurrent_session_creation(self):
        from bahram.core.persistence import SessionStore

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store = SessionStore(db_path=db_path)
            num_sessions = 50

            async def _create_session(idx: str):
                session_id = f"sess_{idx}_{uuid.uuid4().hex[:6]}"
                result = store.create_session(
                    session_id=session_id,
                    user_id=f"user_{idx}",
                    channel="load_test",
                    model="test/model",
                )
                return session_id

            start = time.time()
            tasks = [_create_session(str(i)) for i in range(num_sessions)]
            session_ids = await asyncio.gather(*tasks)
            wall_clock = time.time() - start

            assert len(session_ids) == num_sessions
            assert len(set(session_ids)) == num_sessions, "Duplicate session IDs created"

            for sid in session_ids:
                session = store.get_session(sid)
                assert session is not None, f"Session {sid} not found"

            assert wall_clock < 15.0, f"Session creation took {wall_clock:.1f}s"

    @pytest.mark.asyncio
    async def test_concurrent_message_inserts(self):
        from bahram.core.persistence import SessionStore

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store = SessionStore(db_path=db_path)

            session_id = f"sess_{uuid.uuid4().hex[:6]}"
            store.create_session(session_id=session_id)

            num_messages = 100

            async def _insert_message(idx: int):
                msg = Message(
                    role=MessageRole.USER,
                    content=f"Message {idx} from load test",
                    timestamp=time.time(),
                )
                msg_id = store.add_message(session_id, msg)
                return msg_id

            start = time.time()
            tasks = [_insert_message(i) for i in range(num_messages)]
            msg_ids = await asyncio.gather(*tasks)
            wall_clock = time.time() - start

            assert len(msg_ids) == num_messages
            assert len(set(msg_ids)) == num_messages, "Duplicate message IDs created"

            stored_msgs = store.get_messages(session_id, limit=num_messages + 10)
            assert len(stored_msgs) == num_messages, (
                f"Expected {num_messages} messages, got {len(stored_msgs)}"
            )
            assert wall_clock < 15.0

    @pytest.mark.asyncio
    async def test_concurrent_job_creation(self):
        from bahram.core.engine import Trajectory
        from bahram.core.persistence import SessionStore

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store = SessionStore(db_path=db_path)

            session_id = f"sess_{uuid.uuid4().hex[:6]}"
            store.create_session(session_id=session_id)

            num_jobs = 50

            async def _create_job(idx: int):
                trajectory = Trajectory(
                    run_id=f"job_{idx}_{uuid.uuid4().hex[:6]}",
                    session_id=session_id,
                    goal=f"Job {idx} goal",
                    model="test/model",
                    provider="test",
                    status="completed",
                )
                run_id = store.save_trajectory(trajectory, session_id)
                return run_id

            start = time.time()
            tasks = [_create_job(i) for i in range(num_jobs)]
            run_ids = await asyncio.gather(*tasks)
            wall_clock = time.time() - start

            assert len(run_ids) == num_jobs
            assert len(set(run_ids)) == num_jobs, "Duplicate run IDs created"

            stored_runs = store.get_recent_runs(limit=num_jobs + 10)
            assert len(stored_runs) == num_jobs, (
                f"Expected {num_jobs} runs, got {len(stored_runs)}"
            )
            assert wall_clock < 15.0

    @pytest.mark.asyncio
    async def test_concurrent_tool_call_logging(self):
        from bahram.core.persistence import SessionStore

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store = SessionStore(db_path=db_path)

            session_id = f"sess_{uuid.uuid4().hex[:6]}"
            store.create_session(session_id=session_id)

            run_id = f"run_{uuid.uuid4().hex[:6]}"
            trajectory_runs = __import__("bahram.core.engine", fromlist=["Trajectory"])
            traj = trajectory_runs.Trajectory(
                run_id=run_id,
                session_id=session_id,
                goal="test",
            )
            store.save_trajectory(traj, session_id)

            num_tool_calls = 80

            async def _log_tool(idx: int):
                call_id = store.log_tool_call(
                    run_id=run_id,
                    tool_name=f"tool_{idx % 5}",
                    arguments={"idx": idx},
                    status="success",
                    result=f"result_{idx}",
                    duration_ms=float(idx),
                )
                return call_id

            start = time.time()
            tasks = [_log_tool(i) for i in range(num_tool_calls)]
            call_ids = await asyncio.gather(*tasks)
            wall_clock = time.time() - start

            assert len(call_ids) == num_tool_calls
            assert len(set(call_ids)) == num_tool_calls, "Duplicate tool call IDs"
            assert wall_clock < 15.0


class TestLoadSummary:
    def test_print_summary(self, capsys):
        result = LoadTestResult(
            total_runs=50,
            successful=50,
            failed=0,
            latencies=[0.01, 0.02, 0.015, 0.03, 0.025, 0.01, 0.04, 0.02, 0.018, 0.022],
            wall_clock=0.5,
        )

        summary = (
            f"Runs: {result.total_runs} | "
            f"OK: {result.successful} | "
            f"Failed: {result.failed} | "
            f"Error rate: {result.error_rate:.1%}\n"
            f"Throughput: {result.throughput:.1f} runs/s | "
            f"Wall clock: {result.wall_clock:.3f}s\n"
            f"Latency: avg={result.avg:.4f}s p50={result.p50:.4f}s p95={result.p95:.4f}s"
        )
        assert "50" in summary
        assert "0.0%" in summary
