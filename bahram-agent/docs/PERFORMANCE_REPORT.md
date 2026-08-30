# Performance Report

## Environment

| Parameter | Value |
|-----------|-------|
| Python | 3.14 |
| OS | Linux |
| CPU | Available cores |
| Memory | Available RAM |
| Storage | Local filesystem |

---

## Workload Description

Performance tests use `MockProvider` with configurable delay to measure engine overhead without network latency. Tests exercise:

1. **Provider call latency** — Single LLM call overhead
2. **Tool call latency** — Tool execution + result processing
3. **Smart Context build** — Context window assembly and optimization
4. **Budget recording** — Token/cost tracking throughput
5. **Event emission** — Event creation and persistence
6. **Recovery checkpoint** — Plan serialization and persistence

---

## Test Results

### Provider Latency

| Test | Iterations | Latency | Assertion |
|------|-----------|---------|-----------|
| Single call | 1 | < 5s | `test_single_call_latency` |
| Tool call (2 calls) | 1 | < 5s | `test_tool_call_latency` |

**Note:** MockProvider has 10ms delay. Real provider latency is network-bound (100ms-2s typically).

### Smart Context Performance

| Test | Data Size | Latency | Assertion |
|------|-----------|---------|-----------|
| Context build | 50 messages × 50 words | < 1s | `test_context_build_latency` |
| Context optimization | 100 context windows | < 0.5s | `test_context_optimization_latency` |

**Observation:** Smart context build is dominated by token estimation (`len/4` heuristic). Real tokenization would be 2-5x slower.

### Budget Tracking

| Test | Operations | Latency | Throughput |
|------|-----------|---------|------------|
| Recording (model + tool) | 1000 runs | < 1s | ~1000 runs/s |
| Budget check | 1000 checks | < 0.5s | ~2000 checks/s |

**Observation:** Budget tracking is in-memory. SQLite persistence is not exercised in these tests.

### Event Tracking

| Test | Operations | Latency | Throughput |
|------|-----------|---------|------------|
| Event emission | 1000 events | < 1s | ~1000 events/s |
| Event query | 100 queries × 500 events | < 1s | ~100 queries/s |

**Observation:** Events are appended to JSONL file. Query loads all events into memory.

### Recovery Checkpoint

| Test | Operations | Latency | Throughput |
|------|-----------|---------|------------|
| Checkpoint write | 100 writes × 20 steps | < 2s | ~50 writes/s |

**Observation:** Checkpoint serialization is JSON-based. Large plans (>100 steps) may be slower.

---

## Concurrency Levels

| Level | Tested | Notes |
|-------|--------|-------|
| Sequential (1) | Yes | All performance tests |
| Concurrent (5) | No | Not tested |
| Concurrent (10) | No | Not tested |
| Concurrent (50) | No | Not tested |

**Gap:** No concurrent load testing. Sequential benchmarks only.

---

## Latency Percentiles

Not measured — tests assert upper bounds only.

| Metric | Measured | Target | Status |
|--------|----------|--------|--------|
| p50 engine latency | Not measured | < 2s | UNVERIFIED |
| p95 engine latency | Not measured | < 5s | UNVERIFIED |
| p99 engine latency | Not measured | < 10s | UNVERIFIED |
| Tool execution p50 | Not measured | < 500ms | UNVERIFIED |
| Context build p50 | < 1s (50 msgs) | < 500ms | PARTIAL |

---

## Error Rate

| Scenario | Tested | Result |
|----------|--------|--------|
| Provider timeout | Yes (chaos tests) | Fallback triggered |
| Budget exceeded | Yes (chaos tests) | Run stopped |
| Circuit breaker open | Yes (chaos tests) | Fallback triggered |
| Concurrent tool calls | No | UNVERIFIED |

---

## Limitations

1. **MockProvider** — All tests use mock providers with artificial delays. Real network latency not captured.
2. **Sequential execution** — No concurrent request testing.
3. **In-memory only** — Budget and event tests do not exercise SQLite persistence under load.
4. **Token estimation** — `len/4` heuristic is fast but inaccurate. Real tokenization would add latency.
5. **No p50/p95/p99** — Only upper-bound assertions, no percentile distribution.
6. **No throughput measurement** — No requests/second metric under load.
7. **No memory profiling** — No measurement of memory usage under load.
8. **No real MCP testing** — MCP tool execution not benchmarked.

---

## Recommendations

1. **Add concurrent load tests** — Test with 10/50/100 concurrent requests
2. **Measure real provider latency** — Use actual API with opt-in flag
3. **Add percentile reporting** — p50/p95/p99 latency distribution
4. **Add throughput metrics** — Requests/second under load
5. **Add memory profiling** — Track memory usage during load tests
6. **Benchmark SQLite under load** — Test concurrent writes to jobs/events DB
