# Bahram Autonomy Layer

## Overview

The autonomy layer transforms Bahram from a reactive chat agent into an autonomous task manager. It implements the full loop: understand → plan → execute → observe → verify → replan → delegate → recover → learn → improve.

## Architecture

```
USER GOAL
    ↓
AGENT RUNTIME (agent.py)
    ↓
┌─────────────┼─────────────┐
↓             ↓             ↓
MEMORY        PLANNER        CONTEXT
    │             │             │
    └─────────────┼─────────────┘
                  ↓
            MODEL ROUTER
                  ↓
                 LLM
                  ↓
           ACTION DECISION
                  ↓
         ┌────────┴────────┐
         ↓                 ↓
        TOOL            DELEGATE
         ↓                 ↓
     TOOL PIPELINE     SUBAGENT
         ↓                 ↓
     OBSERVATION      STRUCTURED RESULT
         │                 │
         └────────┬────────┘
                  ↓
             PLAN UPDATE
                  ↓
              REPLANNER
                  ↓
             VERIFICATION
                  ↓
             FINAL RESULT
                  ↓
           TRAJECTORY STORE
                  ↓
          OUTCOME ANALYZER
                  ↓
            LEARNING LOOP
                  ↓
               SKILLS
                  ↓
           FUTURE RETRIEVAL
```

## Components

### 1. Plan (plan.py)

Structured plan representation with DAG dependency support.

- **Plan**: Top-level plan with goal, strategy, status, success criteria
- **PlanStep**: Individual step with dependencies, tools, verification criteria
- **Statuses**: CREATED → PLANNING → READY → EXECUTING → COMPLETED/FAILED/CANCELLED
- **StepStatuses**: PENDING → READY → RUNNING → COMPLETED/FAILED/REPLANNED/SKIPPED/CANCELLED
- **DAG support**: cycle detection, dependency validation, ready-step calculation

### 2. Planner (planner.py)

LLM-driven planner with fallback templates.

- Analyzes goal complexity
- Creates structured plans with dependencies
- Estimates required tools and capabilities
- Includes verification criteria per step
- Falls back to template plans when no LLM provider is configured
- Supports replanning via `replan()` method

### 3. Verification Engine (verification.py)

Reusable verification abstraction.

- **Command verification**: Run shell commands, check exit codes
- **File existence**: Verify files exist or don't exist
- **Content checks**: Contains/not_contains/min_length/max_length
- **Test execution**: Run test suites, check results
- **Schema validation**: Verify JSON structure
- **Custom verifiers**: Register callable verifiers

### 4. Replanner (replanner.py)

Intelligent replanning engine.

- Classifies failures: timeout, permission denial, missing resource, invalid output, network error, budget exceeded, max retries
- Strategies: RETRY, MODIFY_STEP, INSERT_STEP, SKIP, REPLAN, ABORT
- Minimal repair: preserves completed work
- Configurable max replan attempts

### 5. Plan Executor (executor.py)

Executes plans through the agent engine.

- Validates dependencies before execution
- Resolves tools per step
- Executes through ToolExecutor with security pipeline
- Captures results and tool calls
- Evaluates verification criteria
- Triggers replanning on failure

### 6. Subagent Engine (subagent.py)

Real subagent orchestration with capability isolation.

- Spawns isolated agent runs
- Tool filtering (child ≤ parent capabilities)
- Context minimization (only objective + relevant context)
- Timeout enforcement
- Cancellation support
- Structured SubagentResult with evidence and metrics

### 7. Background Job Engine (jobs.py)

Durable SQLite-backed job queue.

- Persistent job state across restarts
- Job priority: LOW, NORMAL, HIGH, CRITICAL
- Automatic retry with exponential backoff
- Concurrent job execution with limits
- Job cancellation
- Handler registration system

### 8. Recovery Manager (recovery.py)

Checkpoint-based crash recovery.

- Checkpoints plan state after meaningful boundaries
- Resumes interrupted runs
- Validates safe resumption criteria
- Cleanup of old checkpoints

### 9. Learning Engine (learning.py)

Outcome analysis and lesson extraction.

- Analyzes trajectories for success/failure patterns
- Extracts reusable lessons from failures
- Generates skill candidates from validated lessons
- Persists lessons and skills to disk
- Retrieves relevant skills by trigger matching

### 10. Skill Lifecycle (skill_lifecycle.py)

Skill generation, validation, and reuse.

- Generate skills from lesson collections
- Validate skills through usage tracking
- Promotion: candidate → tested → trusted
- Demotion on repeated failures
- Confidence scoring

### 11. Budget Manager (budget.py)

Token/cost budget enforcement.

- Per-session, per-run, per-step tracking
- Warning at configurable threshold (default 80%)
- Exceeding limits reported for controlled termination
- Tracks: input/output tokens, model calls, tool calls, subagent calls

### 12. Event Tracker (events.py)

Structured observability events.

- All events include session_id, run_id, plan_id, step_id correlation
- Events persisted to JSONL file
- Query by type, session, run
- Event types: plan_created, step_started, step_completed, step_failed, replanned, subagent_spawned, budget_warning, etc.

## Integration with Agent

The Agent class (`agent.py`) integrates all components:

```python
agent = Agent(config)
await agent.start()  # Initializes providers, tools, memory, skills, autonomy layer

# Simple chat
response = await agent.chat("hello")

# Planning mode
response = await agent.run_with_plan("fix the login bug")

# Subagent delegation
result = await agent.delegate_to_subagent("research caching patterns")

# Background jobs
job = await agent.create_background_job("analysis", session_id)

# Learning
analysis = await agent.analyze_and_learn(run_id, goal, steps, results, success)
```

## Provider Failover

Configured automatically when multiple providers are registered:

```python
await agent.start()  # Auto-configures FallbackProvider with all registered providers
```

The FallbackProvider tries primary → fallback1 → fallback2, preventing single-point-of-failure.

## Testing

290 tests across:
- `tests/test_autonomy.py`: 103 tests for all autonomy modules
- `tests/evaluation/test_benchmarks.py`: 46 E2E autonomy benchmarks (AUTO-01 through AUTO-20)
- `tests/`: 141 existing tests (agent, core, e2e, memory, providers, persistence, tools)

Run all tests:
```bash
python3 -m pytest tests/ -q --ignore=tests/redteam -k "not fetch"
```

Run autonomy tests only:
```bash
python3 -m pytest tests/test_autonomy.py tests/evaluation/test_benchmarks.py -q
```
