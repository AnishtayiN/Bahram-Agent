# Phase 8 System Trace

## Runtime Call Paths

### 1. User Message → Agent Response (Non-Planning)

```
ENTRY: Agent.run(message)
  → Agent.create_session() / get session
  → Context.get_or_create(session_id)
  → SmartContext.set_system_prompt()
  → Agent._retrieve_memories(message) → SemanticMemory.get_context()
  → Agent._retrieve_skills(task) → SkillManager.find_skill() + SkillLifecycle.get_trusted_skills()
  → SmartContext.add_context(memories, priority=3)
  → SmartContext.add_history("user", message)
  → SmartContext.optimize() → removes low-priority windows if over budget
  → SmartContext.build_messages() → returns list[Message] with priority ordering
  → ContextCompressor.compress() (if messages > 20)
  → AgentEngine.run(messages)
    → AgentEngine.get_provider(model) → checks CircuitBreaker → falls back to __fallback__
    → provider.complete(messages, tools)
    → BudgetManager.record_model_call()
    → ToolExecutor.execute(tool_call) → ApprovalSystem.check_command()
    → BudgetManager.record_tool_call()
    → trajectory recording
  → Agent stores assistant message to Context + Persistence + SmartContext
  → Agent._store_memory()
```

**Status: REAL** — All subsystems wired and active.

### 2. User Message → Agent Response (Planning)

```
ENTRY: Agent.run(message, use_planning=True)
  → [Same context/memory/skill loading as above]
  → Planner.create_plan(goal) → LLM call or keyword fallback
  → PlanExecutor.execute_plan(plan)
    → For each step: _execute_step()
      → provider.complete() for step-specific reasoning
      → ToolExecutor.execute() for tool calls
      → VerificationEngine.verify() if criteria set
      → On failure: Replanner.handle_step_failure() (6 strategies)
      → RecoveryManager.checkpoint() after each successful step
    → EventTracker emits step events
  → Agent.analyze_and_learn() → LearningEngine.analyze_outcome()
  → SkillLifecycle.generate_from_lessons() if lessons ≥ 2
```

**Status: REAL** — Full planning/replanning/verification/checkpointing/learning loop.

### 3. Tool Execution Pipeline

```
AgentEngine._tool_executor.execute(tool_call)
  → ToolExecutor checks tool exists in self.tools
  → ApprovalSystem.check_command(cmd) → checks blocklist + dangerous patterns
  → ApprovalSystem.assess_risk(cmd) → critical/high/medium/low
  → If critical/high: BLOCKED
  → tool.execute(**arguments) with timeout
  → BudgetManager.record_tool_call()
  → EventTracker (via engine)
```

**Status: REAL** — Single executor, single security boundary.

### 4. Provider Failover

```
AgentEngine.run() iteration start
  → get_provider(model)
    → Extract provider name from model string
    → Check CircuitBreaker.can_execute(provider_name)
    → If circuit OPEN → _get_fallback_provider() → tries __fallback__ → first available
    → Return provider
  → provider.complete()
    → On success: record_provider_success() → CircuitBreaker.record_success()
    → On failure: record_provider_failure() → CircuitBreaker.record_failure()
      → _get_fallback_provider() → fallback.complete()
      → On fallback failure: return error
```

**Status: REAL** — Circuit breaker with CLOSED/OPEN/HALF_OPEN states.

### 5. Smart Context Pipeline

```
Agent.run()
  → SmartContext.set_system_prompt(system_prompt)
  → SmartContext.add_context(memories, priority=3, metadata={source: "memory"})
  → SmartContext.add_context(skills, priority=2, metadata={source: "skills"})
  → SmartContext.add_history("user", message)
  → SmartContext.optimize() → removes lowest-priority windows if over budget
  → SmartContext.build_messages() → returns Message objects sorted by priority
    → System prompt (always included)
    → Context windows (sorted by priority, up to 70% budget)
    → History messages (in reverse order, up to 90% budget)
  → If messages > 20: ContextCompressor.compress() → heuristic or model-based
```

**Status: REAL** — SmartContext is the primary context source for the engine.

### 6. Memory Pipeline

```
Agent._retrieve_memories(query)
  → SemanticMemory.get_context(query, max_memories=5)
    → SQLite FTS5 search
    → Returns formatted context string
  → Prepended to user message

Agent._store_memory(query, response)
  → SemanticMemory.add(f"User: {query}\nAssistant: {response}", source="conversation")
```

**Status: REAL** — FTS5-backed semantic memory with retrieval and storage.

### 7. Security Pipeline

```
ToolExecutor.execute(tool_call)
  → ApprovalSystem.check_command(cmd)
    → Check HARDLINE_BLOCKLIST (rm -rf /, fork bombs, etc.)
    → Check user deny patterns
    → Check allowlist
    → Check DANGEROUS_PATTERNS (35+ regex patterns)
  → ApprovalSystem.assess_risk(cmd) → critical/high/medium/low
  → If critical/high: return blocked result
  → tool.execute()
```

**Status: REAL** — All tool paths go through the same security pipeline.

### 8. Event Tracking

```
EventTracker.emit(event_type, session_id, run_id, **kwargs)
  → Stores in-memory list
  → Appends to JSONL file (data/events/events.jsonl)
  → query_events() for filtering
  → get_trace() for correlation
```

Events emitted:
- plan_created, plan_updated
- step_started, step_completed, step_failed
- replanned
- subagent_spawned, subagent_completed
- job_started, job_checkpointed, job_resumed
- provider_fallback
- memory_retrieved, skill_selected, skill_promoted
- budget_warning, budget_exceeded

**Status: REAL** — All event types have correct signatures and callers.

### 9. Recovery Pipeline

```
RecoveryManager.checkpoint(run_id, plan, context_summary)
  → Serialize plan state + completed steps to JSON
  → Save to data/recovery/recovery_checkpoints.json

RecoveryManager.resume_plan(checkpoint)
  → Reconstruct Plan from checkpoint
  → Mark completed steps as COMPLETED
  → Reset running steps to PENDING
  → Return resumable Plan
```

Called automatically by PlanExecutor after each successful step.

**Status: REAL** — Auto-checkpointing during plan execution.

### 10. Learning Pipeline

```
Agent.analyze_and_learn(run_id, goal, steps, results, success)
  → LearningEngine.analyze_outcome()
    → Analyzes trajectory steps and tool results
    → Extracts lessons based on patterns
    → Persists to data/learning/lessons.json
  → SkillLifecycle.generate_from_lessons(lessons)
    → Creates SkillCandidate from lessons
    → Sets status="candidate", confidence=0.3
  → SkillLifecycle.validate(skill_id)
    → Confidence-based promotion: candidate → tested → trusted
```

**Status: REAL** — Lessons extracted, skills generated and promoted.

### 11. Skill Retrieval

```
Agent._retrieve_skills(task)
  → SkillManager.find_skill(task) → file-based skills
  → SkillLifecycle.get_trusted_skills() → auto-generated trusted skills
  → Returns combined context string
```

**Status: REAL** — Both file-based and auto-generated skills retrieved.

## Disconnected Paths (Resolved in Phase 8)

| Path | Before | After |
|------|--------|-------|
| SmartContext output | Written to but never read | `build_messages()` → engine input |
| ContextCompressor | Never called | Called when messages > 20 |
| SkillLifecycle | Trusted skills never retrieved | `get_trusted_skills()` in `_retrieve_skills()` |
| Recovery checkpoints | Manual only | Auto-checkpointed after each step |
| Event signatures | Mismatched callers | Fixed all callers to match signatures |
| Telegram /status | Crashed on `get_total_usage` | Fixed to `get_all_usage()` |
| chat_streaming | No persistence, no smart context | Full persistence + smart context |
