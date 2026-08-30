# Phase 11 Reality Audit

## Methodology

Each feature was audited by tracing its actual entry points, call paths, runtime integration, security coverage, persistence, observability wiring, and test coverage. Statuses are based on evidence in the source code, not documentation claims.

**Status Definitions:**
- **REAL** — Fully implemented, integrated, persisted, secure, and tested
- **PARTIAL** — Implemented but with gaps (missing persistence, security, or tests)
- **UNWIRED** — Code exists but is not connected to the runtime
- **BROKEN** — Code exists but does not function as described

---

## Feature Audit

### 1. Agent Runtime

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `Agent.run()` at `agent.py:216` | ✅ REAL |
| State machine | `RunState` enum in `engine.py:26` (CREATED → LOADING → PLANNING → THINKING → TOOL_PENDING → SECURITY_CHECK → TOOL_EXECUTING → OBSERVING → REPLANNING → COMPLETED/FAILED/CANCELLED/TIMEOUT) | ✅ REAL |
| Cancellation | `engine.cancel()` / `engine._cancel_event` at `engine.py:297` | ✅ REAL |
| Config limits | `RunConfig` at `engine.py:144` (max_iterations, max_runtime_seconds, max_tool_calls, tool_timeout_seconds) | ✅ REAL |
| Smart context integration | `agent.py:40` creates `SmartContextManager`, wired into `run()` at `agent.py:235-263` | ✅ REAL |
| Persistence | `SessionStore` at `agent.py:43`, SQLite-backed sessions and messages | ✅ REAL |
| Observability | `EventTracker` wired at `agent.py:94`, `set_event_tracker()` at `agent.py:137` | ✅ REAL |
| Test coverage | 20 integration + 103 autonomy + 111 phase10 tests | ✅ REAL |

**Status: REAL**

---

### 2. Agent Loop (Engine.run)

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `AgentEngine.run()` at `engine.py:313` | ✅ REAL |
| Provider call | `provider.complete(messages, tools_schema)` at `engine.py:369` | ✅ REAL |
| Tool execution | `ToolExecutor.execute(tool_call, timeout)` at `engine.py:420` | ✅ REAL |
| Budget enforcement | `self._budget_manager.check_budget(run_id)` at `engine.py:353` | ✅ REAL |
| Circuit breaker | `self._circuit_breaker.can_execute()` at `engine.py:260` | ✅ REAL |
| Fallback provider | `_get_fallback_provider()` at `engine.py:268` | ✅ REAL |
| Trajectory recording | `Trajectory` + `TrajectoryStep` appended at `engine.py:444` | ✅ REAL |
| Max iterations | Loop bounded by `run_cfg.max_iterations` at `engine.py:339` | ✅ REAL |
| Max tool calls | Bounded by `run_cfg.max_tool_calls` at `engine.py:409` | ✅ REAL |
| Test coverage | 20 integration + 103 autonomy tests | ✅ REAL |

**Status: REAL**

---

### 3. Planning

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `Planner.create_plan()` called at `agent.py:285` | ✅ REAL |
| LLM planner | `planner.py` — uses provider for plan generation | ✅ REAL |
| Fallback templates | Keyword-based template selection in `planner.py` | ✅ REAL |
| DAG dependencies | `PlanStep.dependencies` field, cycle detection in planner | ✅ REAL |
| Verification | `VerificationEngine.verify()` at `agent.py:292` | ✅ REAL |
| Integration | `agent.run(use_planning=True)` routes through `_plan_executor.execute_plan()` | ✅ REAL |
| Test coverage | 103 autonomy tests | ✅ REAL |

**Status: REAL**

---

### 4. Replanning

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `Replanner.handle_step_failure()` in `replanner.py` | ✅ REAL |
| 6 strategies | Strategy selection in `replanner.py` | ✅ REAL |
| Failure classification | Error type → strategy mapping | ✅ REAL |
| Minimal repair | Replanner attempts minimal fix before full replan | ✅ REAL |
| Max replan attempts | Configured via `max_replan_attempts=3` at `agent.py:103` | ✅ REAL |
| Integration | Called from `PlanExecutor` after step failure | ✅ REAL |
| Test coverage | 103 autonomy tests | ✅ REAL |

**Status: REAL**

---

### 5. Verification

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `VerificationEngine.verify()` called in `PlanExecutor` | ✅ REAL |
| 6 types | command, file, content, test, schema, custom verifiers | ✅ REAL |
| Custom verifiers | Extensible via `VerificationEngine` | ✅ REAL |
| Integration | Wired into `PlanExecutor` at `agent.py:108` | ✅ REAL |
| Test coverage | 103 autonomy tests | ✅ REAL |

**Status: REAL**

---

### 6. Tool System

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `init_tools()` at `tools/__init__.py:8` | ✅ REAL |
| Registered tools | 11 tools (see TOOL_REGISTRY_AUDIT.md) | ✅ REAL |
| MCP adapter | `_MCPToolAdapter` at `agent.py:562`, registered in `_init_mcp_tools()` | ✅ REAL |
| Security pipeline | `ToolExecutor.execute()` → `ApprovalSystem.check_command()` at `engine.py:166` | ✅ REAL |
| Tool schema | All tools implement `schema()` via `BaseTool` | ✅ REAL |
| Execution | `asyncio.wait_for(tool.execute(**args), timeout)` at `engine.py:181` | ✅ REAL |
| Test coverage | 20 integration + 11 phase10 tests | ✅ REAL |

**Status: REAL**

---

### 7. Smart Context

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `SmartContextManager` created at `agent.py:40` | ✅ REAL |
| Budget-aware | `max_tokens` enforced, `optimize()` removes low-priority windows | ✅ REAL |
| Priority windows | `add_context(content, priority, metadata)` at `smart_context.py:32` | ✅ REAL |
| Compression | Triggered at `agent.py:269` when messages > 20 | ✅ REAL |
| build_messages() | Returns `Message` objects at `smart_context.py:125`, used at `agent.py:263` | ✅ REAL |
| Token estimation | `len(text) // 4` heuristic at `smart_context.py:75` | ✅ REAL |
| Observability | Budget warning emitted at `agent.py:257` | ✅ REAL |
| Test coverage | 12 chaos + 9 perf + 6 phase11 tests | ✅ REAL |

**Status: REAL**

---

### 8. Context Compressor

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `ContextCompressor.compress()` at `compressor.py:26` | ✅ REAL |
| Heuristic mode | `_heuristic_compress()` — keeps last N messages + system prompt | ✅ REAL |
| Model-based mode | `_model_compress()` — sends compression prompt to LLM | ✅ REAL |
| Integration | Called at `agent.py:269-281` for long contexts | ✅ REAL |
| Test coverage | 9 perf tests, compression logic tested | ✅ REAL |

**Status: REAL**

---

### 9. Memory

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `SemanticMemory` created at `agent.py:184` | ✅ REAL |
| Storage | SQLite with FTS5 virtual table at `semantic.py:47` | ✅ REAL |
| Search | FTS5 MATCH query at `semantic.py:84`, LIKE fallback at `semantic.py:98` | ✅ REAL |
| Retrieval | `_retrieve_memories()` at `agent.py:507`, injected into context at `agent.py:242` | ✅ REAL |
| Storage (auto) | `_store_memory()` at `agent.py:516`, stores Q&A pairs | ✅ REAL |
| Cross-session | Sessions share the same `memory.db` | ✅ REAL |
| Isolation | Not enforced — all sessions query the same memory store | ⚠️ PARTIAL |
| Test coverage | 103 autonomy + 11 phase10 + 11 phase11 tests | ✅ REAL |

**Status: PARTIAL** — No session isolation; all sessions share memory.

---

### 10. Learning

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `LearningEngine.analyze_outcome()` at `learning.py:140` | ✅ REAL |
| Lesson extraction | `_extract_lesson()` at `learning.py:195` | ✅ REAL |
| Skill generation | `generate_skill()` at `learning.py:234` | ✅ REAL |
| Auto-trigger | `analyze_and_learn()` at `agent.py:296` called after plan execution | ✅ REAL |
| Persistence | JSON files: `lessons.json`, `skill_candidates.json` at `learning.py:105-126` | ✅ REAL |
| Validation | `validate_skill()` at `learning.py:285` — confidence-based promotion | ✅ REAL |
| Test coverage | 103 autonomy + 6 phase11 tests | ✅ REAL |

**Status: REAL**

---

### 11. Skill Lifecycle

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `SkillLifecycle` created at `agent.py:99` | ✅ REAL |
| Generate from lessons | `generate_from_lessons()` at `skill_lifecycle.py:24` | ✅ REAL |
| Validate | `validate()` at `skill_lifecycle.py:39` → `LearningEngine.validate_skill()` | ✅ REAL |
| Record usage | `record_usage()` at `skill_lifecycle.py:47` | ✅ REAL |
| Trusted skills | `get_trusted_skills()` at `skill_lifecycle.py:51` | ✅ REAL |
| Integration | Trusted skills injected into context at `agent.py:537` | ✅ REAL |
| Test coverage | 103 autonomy + 4 phase11 tests | ✅ REAL |

**Status: REAL**

---

### 12. Subagents

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `SubagentEngine.spawn()` at `subagent.py:75` | ✅ REAL |
| Isolation | Separate `RunConfig`, own tool loop at `subagent.py:204` | ✅ REAL |
| Capability restriction | `allowed_tools` filter at `subagent.py:234` | ✅ REAL |
| Timeout | `asyncio.wait_for()` at `subagent.py:114` | ✅ REAL |
| Cancellation | `cancel_event` at `subagent.py:108` | ✅ REAL |
| Event tracking | `emit_subagent_spawned` / `emit_subagent_completed` at `subagent.py:103-151` | ✅ REAL |
| Concurrency | Bounded by `_max_concurrent` (not enforced in current code — see note) | ⚠️ PARTIAL |
| Integration | `Agent.delegate_to_subagent()` at `agent.py:352` | ✅ REAL |
| Test coverage | 103 autonomy + 11 phase10 tests | ✅ REAL |

**Status: PARTIAL** — Concurrency bound declared but not enforced in `SubagentEngine`.

---

### 13. Background Jobs

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `JobEngine.enqueue()` at `jobs.py:201` | ✅ REAL |
| Persistence | SQLite with WAL mode at `jobs.py:115` | ✅ REAL |
| Priority | `JobPriority` enum (LOW/NORMAL/HIGH/CRITICAL) at `jobs.py:30` | ✅ REAL |
| Retry | Exponential backoff at `jobs.py:284` (min(30, 2^attempt)) | ✅ REAL |
| Cancellation | `cancel_job()` at `jobs.py:294` | ✅ REAL |
| Event tracking | `emit_job_started` / `emit_job_checkpointed` at `jobs.py:227-274` | ✅ REAL |
| Max concurrent | `_max_concurrent=3` at `jobs.py:95`, enforced at `jobs.py:234` | ✅ REAL |
| Integration | `Agent.create_background_job()` at `agent.py:371` | ✅ REAL |
| Test coverage | 103 autonomy + 11 phase10 + 6 phase11 tests | ✅ REAL |

**Status: REAL**

---

### 14. Recovery

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `RecoveryManager.checkpoint()` at `recovery.py:76` | ✅ REAL |
| Persistence | JSON file at `data/recovery/recovery_checkpoints.json` | ✅ REAL |
| Checkpoint data | `CheckpointData` with run_id, plan_state, completed_steps, context_summary | ✅ REAL |
| Resume | `resume_plan()` at `recovery.py:130` — reconstructs Plan from checkpoint | ✅ REAL |
| Safety check | `can_safely_resume()` at `recovery.py:145` | ✅ REAL |
| Cleanup | `cleanup_old()` at `recovery.py:158` — removes old checkpoints | ✅ REAL |
| Integration | `Agent.checkpoint_run()` at `agent.py:414` | ✅ REAL |
| Test coverage | 103 autonomy + 6 phase11 tests | ✅ REAL |

**Status: REAL**

---

### 15. Provider Routing

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `AgentEngine.get_provider()` at `engine.py:255` | ✅ REAL |
| Name-based routing | Model string split on "/" at `engine.py:256` | ✅ REAL |
| Fallback | `_get_fallback_provider()` at `engine.py:268` | ✅ REAL |
| Circuit breaker integration | `can_execute()` check at `engine.py:260` | ✅ REAL |
| FallbackProvider | Auto-configured in `_init_provider_failover()` at `agent.py:120` | ✅ REAL |
| Test coverage | 12 chaos + 8 phase10 tests | ✅ REAL |

**Status: REAL**

---

### 16. Provider Health (Circuit Breaker)

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `CircuitBreaker` at `circuit_breaker.py:22` | ✅ REAL |
| States | CLOSED → OPEN (after 5 failures) → HALF_OPEN (after 300s) → CLOSED (on success) | ✅ REAL |
| Record failure | `record_failure()` at `circuit_breaker.py:46` | ✅ REAL |
| Record success | `record_success()` at `circuit_breaker.py:36` | ✅ REAL |
| Can execute | `can_execute()` at `circuit_breaker.py:56` | ✅ REAL |
| Status | `get_status()` at `circuit_breaker.py:81` | ✅ REAL |
| Integration | Wired into `AgentEngine.__init__()` at `engine.py:228` | ✅ REAL |
| Test coverage | 12 chaos + 6 phase11 tests | ✅ REAL |

**Status: REAL**

---

### 17. Failover

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `FallbackProvider.complete()` at `fallback.py:22` | ✅ REAL |
| Chain retry | Primary → fallbacks list at `fallback.py:35` | ✅ REAL |
| Stream support | `FallbackProvider.stream()` at `fallback.py:46` | ✅ REAL |
| Current provider tracking | `_current` field at `fallback.py:17` | ✅ REAL |
| Integration | Registered as `"__fallback__"` at `agent.py:127` | ✅ REAL |
| Idempotency | No guard against duplicate side effects | ⚠️ PARTIAL |
| Test coverage | 12 chaos + 8 phase10 tests | ✅ REAL |

**Status: PARTIAL** — No idempotency guard for duplicate side effects on retry.

---

### 18. Budgeting

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `BudgetManager` at `budget.py:58` | ✅ REAL |
| Token budgets | `max_input_tokens`, `max_output_tokens`, `max_total_tokens` at `budget.py:12` | ✅ REAL |
| Model call limits | `max_model_calls` at `budget.py:16` | ✅ REAL |
| Tool call limits | `max_tool_calls` at `budget.py:17` | ✅ REAL |
| Subagent call limits | `max_subagent_calls` at `budget.py:18` | ✅ REAL |
| Warning thresholds | `warning_threshold=0.8` at `budget.py:19` | ✅ REAL |
| Enforcement | `check_budget()` at `budget.py:155`, called at `engine.py:353` | ✅ REAL |
| Cost estimation | `MODEL_PRICING` in `cost.py:13`, `estimate_cost()` at `cost.py:36` | ✅ REAL |
| Integration | Wired at `agent.py:95`, `engine.set_budget_manager()` at `agent.py:135` | ✅ REAL |
| Test coverage | 12 chaos + 9 perf + 11 phase10 + 8 phase11 tests | ✅ REAL |

**Status: REAL**

---

### 19. Cost Accounting

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `estimate_cost()` at `cost.py:36` | ✅ REAL |
| MODEL_PRICING | 8 models: Claude Sonnet 4, Claude 3.5 Sonnet, Claude 3 Haiku, GPT-4o, GPT-4o-mini, GPT-3.5-turbo, Gemini 2.0 Flash, Gemini 1.5 Pro | ✅ REAL |
| Fallback pricing | Provider-prefix fallback at `cost.py:40-44` | ✅ REAL |
| get_pricing_info | Returns raw pricing dict at `cost.py:53` | ✅ REAL |
| Integration with BudgetManager | Not wired — `BudgetManager.record_model_call()` does not call `estimate_cost()` | ❌ UNWIRED |
| Test coverage | 8 phase11 tests (test_cost_accounting.py) | ✅ REAL |

**Status: PARTIAL** — Cost estimation module exists and is tested, but not wired into BudgetManager.

---

### 20. Security (Approval System)

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `ApprovalSystem` at `approval.py:87` | ✅ REAL |
| Hardline blocklist | 6 patterns at `approval.py:30` | ✅ REAL |
| Dangerous patterns | 30+ regex patterns at `approval.py:39` | ✅ REAL |
| Risk assessment | `assess_risk()` at `approval.py:147` — critical/high/medium/low | ✅ REAL |
| Allowlist | `_is_in_allowlist()` at `approval.py:114` | ✅ REAL |
| Should prompt | `should_prompt()` at `approval.py:133` | ✅ REAL |
| ToolExecutor integration | `engine.py:166-176` — blocks critical/high risk | ✅ REAL |
| Replay defense | Approved commands tracked in `_session_allowlist` | ✅ REAL |
| Test coverage | 20 integration + 16 phase10 + 14 redteam + 11 phase11 tests | ✅ REAL |

**Status: REAL**

---

### 21. Observability (Event Tracker)

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `EventTracker` at `events.py:44` | ✅ REAL |
| Event types | 17: plan_created, plan_updated, step_started, step_completed, step_failed, replanned, subagent_spawned, subagent_completed, job_started, job_checkpointed, job_resumed, provider_fallback, memory_retrieved, skill_selected, skill_promoted, budget_warning, budget_exceeded | ✅ REAL |
| Persistence | JSONL file at `data/events/events.jsonl` at `events.py:48` | ✅ REAL |
| Query | `query_events()` at `events.py:165` — filter by type/session/run | ✅ REAL |
| Trace | `get_trace(run_id)` at `events.py:181` | ✅ REAL |
| Integration | Wired into engine, plan executor, job engine, subagent engine | ✅ REAL |
| Test coverage | 12 chaos + 9 perf + 6 phase11 tests | ✅ REAL |

**Status: REAL**

---

### 22. Persistence (Jobs)

| Aspect | Evidence | Status |
|--------|----------|--------|
| Engine | SQLite with WAL mode at `jobs.py:112` | ✅ REAL |
| Schema | 19 columns, 4 indexes at `jobs.py:117-143` | ✅ REAL |
| Thread safety | `threading.local()` connection at `jobs.py:99` | ✅ REAL |
| Crash recovery | `_load_pending_jobs()` at `jobs.py:146` — finds running/starting/retrying jobs on restart | ✅ REAL |
| Test coverage | 20 integration + 11 phase10 + 6 phase11 tests | ✅ REAL |

**Status: REAL**

---

### 23. MCP Integration

| Aspect | Evidence | Status |
|--------|----------|--------|
| Entry point | `Agent._init_mcp_tools()` at `agent.py:140` | ✅ REAL |
| Client | `MCPClient` from `bahram.mcp.client` | ✅ REAL |
| Discovery | `client.connect()` + `client.list_tools()` at `agent.py:152-153` | ✅ REAL |
| Adapter | `_MCPToolAdapter` at `agent.py:562` — wraps MCP tools for ToolExecutor | ✅ REAL |
| Security | MCP tools go through same ToolExecutor → ApprovalSystem pipeline | ✅ REAL |
| Fixture server test | `tests/fixtures/mcp/server.py` exists but no real process test | ⚠️ PARTIAL |
| Test coverage | 11 phase10 tests | ✅ REAL |

**Status: PARTIAL** — Discovery and registration work, but no real MCP server process test.

---

### 24. Gateway

| Aspect | Evidence | Status |
|--------|----------|--------|
| Service | `GatewayService` (systemd/launchctl) | ✅ REAL |
| Session routing | Session creation, resume, authorization | ✅ REAL |
| Authorization | User-session mapping, role-based access | ✅ REAL |
| Cancellation | `cancel_session()` delegates to `engine.cancel()` | ✅ REAL |
| Response normalization | Standardized response format | ✅ REAL |
| Test coverage | 20 integration + 10 phase10 + 10 phase11 tests | ✅ REAL |

**Status: REAL**

---

### 25. Telegram

| Aspect | Evidence | Status |
|--------|----------|--------|
| Bot | `TelegramPlatform` — full command set | ✅ REAL |
| Agent dispatch | Routes to `agent.run()` | ✅ REAL |
| Usage stats | Command stats tracked | ✅ REAL |
| Inline approval keyboard | Not implemented | ❌ BROKEN |
| Test coverage | 20 integration tests | ✅ REAL |

**Status: PARTIAL** — Bot works, but inline approval keyboard not implemented.

---

## Summary Matrix

| # | Feature | Status | Evidence |
|---|---------|--------|----------|
| 1 | Agent Runtime | **REAL** | State machine, cancellation, config limits, smart context |
| 2 | Agent Loop | **REAL** | Provider call → tool exec → budget → trajectory |
| 3 | Planning | **REAL** | LLM planner + fallback templates + DAG |
| 4 | Replanning | **REAL** | 6 strategies, failure classification |
| 5 | Verification | **REAL** | 6 types + custom verifiers |
| 6 | Tool System | **REAL** | 11 tools, MCP adapter, security pipeline |
| 7 | Smart Context | **REAL** | Budget-aware, priority windows, compression |
| 8 | Context Compressor | **REAL** | Heuristic + model-based |
| 9 | Memory | **PARTIAL** | FTS5, retrieval, but no session isolation |
| 10 | Learning | **REAL** | Lesson extraction, skill generation |
| 11 | Skill Lifecycle | **REAL** | Generate, validate, promote |
| 12 | Subagents | **PARTIAL** | Isolated runs, but concurrency not enforced |
| 13 | Background Jobs | **REAL** | SQLite, priority, retry, cancellation |
| 14 | Recovery | **REAL** | Checkpoint, resume, cleanup |
| 15 | Provider Routing | **REAL** | Name-based with fallback |
| 16 | Circuit Breaker | **REAL** | CLOSED/OPEN/HALF_OPEN, all transitions |
| 17 | Failover | **PARTIAL** | Chain retry, but no idempotency guard |
| 18 | Budgeting | **REAL** | Token/model/tool/subagent limits |
| 19 | Cost Accounting | **PARTIAL** | Module exists, not wired into BudgetManager |
| 20 | Security | **REAL** | 30+ patterns, risk assessment, ToolExecutor integration |
| 21 | Observability | **REAL** | 17 event types, JSONL persistence |
| 22 | Persistence (Jobs) | **REAL** | SQLite, WAL, crash recovery |
| 23 | MCP Integration | **PARTIAL** | Discovery works, no real server process test |
| 24 | Gateway | **REAL** | Session routing, authorization, cancellation |
| 25 | Telegram | **PARTIAL** | Bot works, no inline approval keyboard |

**Counts:** 18 REAL, 7 PARTIAL, 0 UNWIRED, 0 BROKEN
