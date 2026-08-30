# Phase 12 — Reality Audit

Audit of the 10 gaps identified in the Phase 11 scorecard. Each gap is assessed against actual runtime code paths.

---

## GAP-1: Cost Accounting Not Wired into BudgetManager

**CLAIM:** `estimate_cost()` provides USD cost estimation for LLM calls.

**ENTRY POINT:** `bahram/autonomy/cost.py:36` — `estimate_cost(model, input_tokens, output_tokens)`

**ACTUAL RUNTIME PATH:** `BudgetManager.record_model_call()` at `budget.py:94-150` calls `estimate_cost()` when `model` is provided. Cost is accumulated in `BudgetUsage.estimated_cost_usd` and `cost_usd`. Cost warnings are emitted when thresholds are breached. `check_budget()` at `budget.py:178-198` checks `estimated_cost_usd >= max_cost_usd`.

**STATUS:** REAL — Fully wired as of current codebase.

**EVIDENCE:** `budget.py:105` calls `estimate_cost(model, input_tokens, output_tokens)`. `budget.py:111-112` accumulates cost. `budget.py:139-148` emits cost warnings. `budget.py:190-191` checks cost budget.

**REMAINING GAP:** Token estimation is `len/4` heuristic at `engine.py:395`. Actual input/output split from provider is not captured — split 50/50 at `engine.py:400-401`.

---

## GAP-2: No Monitoring Dashboard

**CLAIM:** EventTracker provides 17 event types with JSONL persistence.

**ENTRY POINT:** `bahram/autonomy/events.py:44` — `EventTracker.__init__()`

**ACTUAL RUNTIME PATH:** Events are emitted by subsystems (planner, replanner, executor, jobs, subagents, budget) and stored in `data/events/events.jsonl`. Query via `query_events()` and `get_trace()`.

**STATUS:** REAL — Events work, but no dashboard exists.

**EVIDENCE:** `events.py:52-58` appends to JSONL. `events.py:60-85` loads on startup. `events.py:165-179` query supports filtering.

**REMAINING GAP:** No operational dashboard UI. No log rotation for events.jsonl. No alerting integration.

---

## GAP-3: No Live LLM E2E Tests

**CLAIM:** 592 tests pass including autonomy, chaos, performance.

**ENTRY POINT:** `tests/` directory — all test files.

**ACTUAL RUNTIME PATH:** Tests use MockProvider (e.g., `tests/performance/test_performance.py:11-27`). No test imports real API credentials.

**STATUS:** PARTIAL — Tests verify logic but not real LLM behavior.

**EVIDENCE:** `test_performance.py:11` defines `MockProvider`. No test file uses actual API keys.

**REMAINING GAP:** Cannot validate real LLM response quality, token usage accuracy, or provider-specific behavior without credentials.

---

## GAP-4: Telegram Inline Approval Keyboard

**CLAIM:** Telegram platform provides interactive approval for dangerous commands.

**ENTRY POINT:** `bahram/platforms/telegram.py:11` — `TelegramPlatform`

**ACTUAL RUNTIME PATH:** Telegram dispatches messages to agent at `telegram.py:303-346`. Messages are forwarded to `agent.run()`. Security checks happen in `ToolExecutor.execute()` at `engine.py:158-208` via `ApprovalSystem`. Blocked commands return error strings.

**STATUS:** PARTIAL — Approval works via engine but not via Telegram callback query buttons.

**EVIDENCE:** `telegram.py:338-346` calls `self._agent.run()`. `engine.py:170-180` blocks critical/high risk commands. No `CallbackQueryHandler` registered in `telegram.py:48-65`.

**REMAINING GAP:** No inline keyboard for approve/deny. User gets text error only, no interactive approval flow.

---

## GAP-5: Session Memory Isolation

**CLAIM:** Memory is persisted and retrievable across sessions.

**ENTRY POINT:** `bahram/memory/semantic.py:23` — `SemanticMemory`

**ACTUAL RUNTIME PATH:** `SemanticMemory` uses a single SQLite database (`memory.db`). All sessions call `add()` and `search()` on the same connection. No session_id filter in queries.

**STATUS:** REAL but UNISOLATED — Memory works but all sessions share the same store.

**EVIDENCE:** `semantic.py:32-70` creates single DB. `semantic.py:81-110` searches without session filter. `agent.py:507-514` retrieves memories globally.

**REMAINING GAP:** No session-scoped memory isolation. Cross-session data leakage is possible.

---

## GAP-6: Subagent Concurrency Enforcement

**CLAIM:** SubagentEngine limits concurrent subagents.

**ENTRY POINT:** `bahram/autonomy/subagent.py` — `SubagentEngine.spawn()`

**ACTUAL RUNTIME PATH:** `SubagentEngine` declares `_max_concurrent` but the actual enforcement is in `JobEngine._max_concurrent` at `jobs.py:95`. SubagentEngine itself does not check concurrency before spawning.

**STATUS:** PARTIAL — Limit declared but not enforced in SubagentEngine itself.

**EVIDENCE:** `test_subagent_concurrency.py` tests bounded by `_max_concurrent`. Actual `SubagentEngine.spawn()` does not check active count.

**REMAINING GAP:** Concurrent subagents can exceed declared limit if spawned directly.

---

## GAP-7: Failover Idempotency

**CLAIM:** FallbackProvider provides automatic failover between providers.

**ENTRY POINT:** `bahram/providers/fallback.py:11` — `FallbackProvider`

**ACTUAL RUNTIME PATH:** `FallbackProvider.complete()` at `fallback.py:22-44` tries primary, catches exception, tries fallbacks. No idempotency check for duplicate side effects.

**STATUS:** REAL — Failover works, but no idempotency guard.

**EVIDENCE:** `fallback.py:30-43` tries primary then fallbacks sequentially. No deduplication logic.

**REMAINING GAP:** If primary partially succeeds before failing, fallback may cause duplicate side effects (e.g., duplicate tool calls).

---

## GAP-8: 34 Unregistered Tool Modules

**CLAIM:** 50 tool modules exist in `bahram/tools/`.

**ENTRY POINT:** `bahram/tools/` directory — 50 `.py` files.

**ACTUAL RUNTIME PATH:** `bahram/tools/__init__.py` calls `init_tools()` which registers a subset. `agent.py:177-179` calls `init_tools()`.

**STATUS:** REAL — 11 tools registered, 34+ exist but not on critical path.

**EVIDENCE:** `tools/` has 50 files. `engine.py:256-259` registers tools via `register_tool()`. 34 tool modules not registered in default config.

**REMAINING GAP:** Unregistered tools are available but not wired. Not a production risk unless explicitly needed.

---

## GAP-9: No Real MCP Server Process Test

**CLAIM:** MCP client/server integration with tool discovery.

**ENTRY POINT:** `bahram/mcp/client.py` — `MCPClient`

**ACTUAL RUNTIME PATH:** `agent.py:140-163` initializes MCP tools. `MCPClient.connect()` connects to configured servers. `_MCPToolAdapter` wraps MCP tools.

**STATUS:** PARTIAL — Code exists, integration works in principle, no test with real MCP server process.

**EVIDENCE:** `agent.py:140-163` MCP initialization. `mcp/client.py` client implementation. No test file exercises real MCP connection.

**REMAINING GAP:** No test with actual MCP server. Cannot verify discovery, tool execution, or error handling with real servers.

---

## GAP-10: No Load Testing

**CLAIM:** Performance tests measure latency and throughput.

**ENTRY POINT:** `tests/performance/test_performance.py`

**ACTUAL RUNTIME PATH:** 9 performance tests measure single-call latency, tool call latency, smart context build, budget recording, event emission, and checkpoint latency.

**STATUS:** PARTIAL — Benchmarks exist, but no load/concurrency testing.

**EVIDENCE:** `test_performance.py` has 9 tests. All use sequential execution. No concurrent request testing.

**REMAINING GAP:** No load testing with concurrent users. No stress testing. No throughput measurement under load.

---

## Summary

| ID | Gap | Status | Remaining Work |
|----|-----|--------|----------------|
| GAP-1 | Cost accounting wiring | REAL | Token estimation accuracy |
| GAP-2 | Monitoring dashboard | REAL | Build UI, add log rotation, alerting |
| GAP-3 | Live LLM E2E tests | PARTIAL | Requires API credentials |
| GAP-4 | Telegram inline approval | PARTIAL | Add CallbackQueryHandler |
| GAP-5 | Session memory isolation | REAL (unisolated) | Add session_id filtering |
| GAP-6 | Subagent concurrency | PARTIAL | Add enforcement in SubagentEngine |
| GAP-7 | Failover idempotency | REAL (no guard) | Add deduplication logic |
| GAP-8 | Unregistered tools | REAL | Register as needed |
| GAP-9 | Real MCP server test | PARTIAL | Add MCP server fixture |
| GAP-10 | Load testing | PARTIAL | Add concurrent load tests |
