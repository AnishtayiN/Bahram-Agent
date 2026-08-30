# Phase 12 — Gap Tracker

Tracking all known gaps with severity, current state, proposed fix, test strategy, and evidence.

---

## GAP-01: Token Estimation Heuristic

| Field | Value |
|-------|-------|
| **ID** | GAP-01 |
| **Problem** | Token counts estimated via `len/4` heuristic. Input/output split is arbitrary 50/50. |
| **Severity** | Medium |
| **Current State** | `engine.py:395-401` — `usage_tokens = len(response.content) // 4`, split 50/50. Cost calculated from these estimates. |
| **Fix** | Parse actual `usage` from provider responses. Most providers return `input_tokens`/`output_tokens` in response metadata. |
| **Test** | Mock provider returns `metadata={"usage": {"input_tokens": 100, "output_tokens": 50}}`. Verify `BudgetManager` records exact counts. |
| **Status** | PARTIAL — Works but inaccurate. Cost estimates may be 20-50% off. |
| **Evidence** | `engine.py:395-401`, `budget.py:105`, `cost.py:48-50` |

---

## GAP-02: No Monitoring Dashboard

| Field | Value |
|-------|-------|
| **ID** | GAP-02 |
| **Problem** | Events stored in JSONL but no operational dashboard for visualization. |
| **Severity** | Low |
| **Current State** | `events.py:52-58` writes JSONL. `events.py:165-179` supports query. No UI. |
| **Fix** | Build simple web dashboard or CLI tool that reads events.jsonl and displays metrics. |
| **Test** | Dashboard loads without error. Displays event counts, latency percentiles, error rates. |
| **Status** | NOT STARTED |
| **Evidence** | `events.py` — event persistence works, no dashboard code exists |

---

## GAP-03: No Live LLM E2E Tests

| Field | Value |
|-------|-------|
| **ID** | GAP-03 |
| **Problem** | All tests use MockProvider. No test exercises real LLM API. |
| **Severity** | Medium |
| **Current State** | 592 tests pass with mocks. Real provider behavior untested. |
| **Fix** | Add opt-in live tests gated by `BAHRAM_LIVE_TEST=1` env var and API key presence. |
| **Test** | `pytest tests/e2e_live/ --live` runs against real API. Verifies response quality, token usage. |
| **Status** | PARTIAL — `tests/e2e_live/` directory exists but no credentials configured. |
| **Evidence** | `tests/e2e_live/` directory exists. No test file found using real API. |

---

## GAP-04: Telegram Inline Approval Keyboard

| Field | Value |
|-------|-------|
| **ID** | GAP-04 |
| **Problem** | Approval works via text error but no interactive approve/deny buttons in Telegram. |
| **Severity** | Low |
| **Current State** | `telegram.py:48-65` registers handlers. No `CallbackQueryHandler`. Security blocks return error text. |
| **Fix** | Add `CallbackQueryHandler` for approve/deny buttons. Store pending approvals, present inline keyboard, process callback. |
| **Test** | Mock Telegram update with callback query. Verify approval system receives approve/deny. |
| **Status** | NOT STARTED |
| **Evidence** | `telegram.py:48-65`, `engine.py:170-180` — security blocks return errors, no interactive flow |

---

## GAP-05: Session Memory Isolation

| Field | Value |
|-------|-------|
| **ID** | GAP-05 |
| **Problem** | All sessions share the same memory store. No session-scoped filtering. |
| **Severity** | Medium |
| **Current State** | `semantic.py:81-110` searches without session filter. `agent.py:507-514` retrieves globally. |
| **Fix** | Add `session_id` column to memories table. Filter searches by session_id. Add cross-session query option. |
| **Test** | Create two sessions. Add memory to session A. Verify session B cannot retrieve it by default. Verify cross-session query works. |
| **Status** | PARTIAL — Memory isolation test exists (`test_memory_isolation.py`) but shared store means isolation is policy-based, not enforced at DB level. |
| **Evidence** | `semantic.py:32-70` — no session_id column. `test_memory_isolation.py` — tests policy-based isolation. |

---

## GAP-06: Subagent Concurrency Enforcement

| Field | Value |
|-------|-------|
| **ID** | GAP-06 |
| **Problem** | `SubagentEngine` declares `_max_concurrent` but does not enforce it before spawning. |
| **Severity** | Low |
| **Current State** | `subagent.py` has `_max_concurrent` attribute. `spawn()` does not check active count. |
| **Fix** | Add active count tracking in `SubagentEngine`. Check `_active_count < _max_concurrent` before spawning. |
| **Test** | Spawn max+1 subagents concurrently. Verify the (max+1)th is queued or rejected. |
| **Status** | PARTIAL — `JobEngine` enforces concurrency at `jobs.py:234`. SubagentEngine delegates to JobEngine for execution. |
| **Evidence** | `subagent.py`, `jobs.py:234` — `self._active_count >= self._max_concurrent` check exists in JobEngine |

---

## GAP-07: Failover Idempotency

| Field | Value |
|-------|-------|
| **ID** | GAP-07 |
| **Problem** | If primary provider partially succeeds before failing, fallback may cause duplicate side effects. |
| **Severity** | Low |
| **Current State** | `fallback.py:30-43` catches exception and tries next provider. No deduplication. |
| **Fix** | Add idempotency keys to tool calls. Check if tool was already executed before running on fallback. |
| **Test** | Mock primary that succeeds tool call then fails. Verify fallback does not re-execute same tool. |
| **Status** | NOT STARTED |
| **Evidence** | `fallback.py:30-43` — sequential try/catch, no deduplication |

---

## GAP-08: Unregistered Tool Modules

| Field | Value |
|-------|-------|
| **ID** | GAP-08 |
| **Problem** | 34 tool modules exist but are not registered in default configuration. |
| **Severity** | Info |
| **Current State** | `bahram/tools/` has 50 files. `init_tools()` registers subset. 34 modules unused. |
| **Fix** | Register tools on-demand based on config. Or document which tools are available by default. |
| **Test** | Verify all documented tools are registered. Verify unregistered tools can be loaded on-demand. |
| **Status** | LOW PRIORITY — Not blocking production. |
| **Evidence** | `tools/` directory listing shows 50 files. |

---

## GAP-09: No Real MCP Server Test

| Field | Value |
|-------|-------|
| **ID** | GAP-09 |
| **Problem** | MCP client/server code exists but no test exercises real MCP server process. |
| **Severity** | Low |
| **Current State** | `mcp/client.py` and `mcp/server.py` exist. `agent.py:140-163` wires MCP. No integration test. |
| **Fix** | Create MCP test fixture that starts a real MCP server process. Test discovery, tool execution, error handling. |
| **Test** | Start mock MCP server. Connect client. List tools. Execute tool. Verify result. Disconnect. |
| **Status** | NOT STARTED |
| **Evidence** | `mcp/client.py`, `mcp/server.py`, `agent.py:140-163` |

---

## GAP-10: No Load Testing

| Field | Value |
|-------|-------|
| **ID** | GAP-10 |
| **Problem** | Performance tests are sequential benchmarks. No concurrent load testing. |
| **Severity** | Medium |
| **Current State** | `tests/performance/test_performance.py` — 9 tests, all sequential. |
| **Fix** | Add load tests with 10/50/100 concurrent requests. Measure p50/p95/p99 latency, error rate, throughput. |
| **Test** | Run 50 concurrent `engine.run()` calls. Verify p95 < 5s, error rate < 5%. |
| **Status** | NOT STARTED |
| **Evidence** | `test_performance.py` — all tests are sequential |

---

## Summary

| Status | Count | IDs |
|--------|-------|-----|
| REAL (no remaining gap) | 1 | GAP-01 (partial accuracy) |
| PARTIAL (mostly working) | 3 | GAP-03, GAP-05, GAP-06 |
| NOT STARTED | 4 | GAP-02, GAP-04, GAP-07, GAP-09 |
| LOW PRIORITY | 2 | GAP-08, GAP-10 |
