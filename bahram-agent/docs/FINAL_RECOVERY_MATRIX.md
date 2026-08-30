# Final Recovery Matrix

| Failure | Detection | Classification | Recovery | Persistence | Expected State | Test |
|---------|-----------|----------------|----------|-------------|----------------|------|
| Provider timeout | `asyncio.TimeoutError` in `provider.complete()` | Provider error | Circuit breaker records failure, fallback to next provider | Circuit state in memory | Provider marked unhealthy, fallback used | `test_circuit_breaker_transitions` |
| Provider 4xx/5xx | Exception in `provider.complete()` | Provider error | Circuit breaker records failure, fallback chain | Circuit state in memory | Primary marked unhealthy | `test_provider_failover` |
| All providers fail | All fallbacks exhaust | Fatal provider error | Return error response to user | Trajectory records error | Run completed with error | `test_all_fail_returns_error` |
| Tool execution error | Exception in `tool.execute()` | Tool error | Error returned to model, model retries or adapts | Tool call logged | Tool result contains error | `test_tool_failure_recovery` |
| Tool timeout | `asyncio.TimeoutError` in `ToolExecutor.execute()` | Timeout | Tool result with timeout error, model adapts | Tool call logged | Tool marked timed out | `test_max_iterations_stops` |
| Budget exceeded | `BudgetManager.check_budget()` returns exceeded | Budget | Run stops with budget message | Budget usage recorded | Run completed with budget limit | `test_budget_check_stops_execution` |
| Max iterations | Loop counter reaches limit | Limit | Run stops with summary message | Trajectory recorded | Run completed with iteration limit | `test_max_iterations_stops` |
| Max runtime | `time.time() - start > max_runtime_seconds` | Timeout | Run stops with timeout message | Trajectory recorded | Run completed with timeout | Tested via RunConfig |
| Max tool calls | `total_tool_calls >= max_tool_calls` | Limit | Run stops with summary message | Trajectory recorded | Run completed with tool limit | Tested via RunConfig |
| Cancel event | `self._cancel_event.is_set()` | Cancellation | Run stops immediately | Trajectory recorded | Run status = cancelled | `test_cancel_stops_execution` |
| Plan step failure | `VerificationEngine.verify()` fails | Verification failure | Replanner classifies and applies strategy | Step status updated | Step retried/modified/skipped/replanned | `test_replanner_strategies` |
| LLM planning failure | Exception in `Planner.create_plan()` | Provider error | Fallback to keyword-based plan | Plan persisted | Plan created with templates | `test_planner_fallback` |
| Context overflow | `SmartContext.optimize()` removes windows | Context limit | Low-priority windows removed, critical preserved | SmartContext state | System prompt + recent history preserved | `test_smart_context_optimize` |
| Memory retrieval failure | Exception in `SemanticMemory.get_context()` | Memory error | Empty context returned, run continues | Memory state unchanged | Run proceeds without memory | `test_memory_retrieval` |
| Skill retrieval failure | Exception in `SkillManager.find_skill()` | Skill error | Empty skill context, run continues | Skill state unchanged | Run proceeds without skills | `test_skill_retrieval` |
| MCP server disconnect | Exception in `MCPClient.call_tool()` | MCP error | Error returned to model | MCP state | Tool call fails, model adapts | MCP error handling |
| Telegram send failure | Exception in `bot.send_message()` | Platform error | Error logged, message dropped | Telegram state | User notified if possible | Telegram error handling |
| SQLite lock | `sqlite3.OperationalError` | Database error | WAL mode handles concurrent access | Database state | Operation retried or failed | Database stress tests |
| Recovery checkpoint fail | Exception in `RecoveryManager.checkpoint()` | Recovery error | Warning logged, run continues | Checkpoint state | Run proceeds without checkpoint | `test_checkpoint_latency` |
| Learning failure | Exception in `LearningEngine.analyze_outcome()` | Learning error | Warning logged, run completes | Learning state | Run completed, learning skipped | Learning error handling |
