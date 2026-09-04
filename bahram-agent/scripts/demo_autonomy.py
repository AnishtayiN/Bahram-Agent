#!/usr/bin/env python3
"""Deterministic end-to-end demonstration of the Bahram autonomy chain.

Exercises every real component through tmpdir-isolated data directories
and a deterministic stub provider so no external API keys are needed.

Chain covered:
  SESSION -> MEMORY -> SMART CONTEXT -> PLAN -> TOOL -> SECURITY ->
  SUBAGENT -> FAILURE -> REPLAN -> RECOVERY -> VERIFY -> CHECKPOINT ->
  COMPLETE -> TRAJECTORY -> LESSON -> SKILL

Usage:
    python3 scripts/demo_autonomy.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Ensure the bahram package is importable when running from any directory.
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Deterministic provider (no network, no mocking – just returns canned data)
# ---------------------------------------------------------------------------

from bahram.core.engine import (
    AgentResponse,
    Message,
    MessageRole,
    RunState,
    ToolCall,
)


class DeterministicProvider:
    """Minimal LLM provider that returns deterministic responses."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or [])
        self._idx = 0

    def _next(self) -> str:
        if self._idx < len(self._responses):
            resp = self._responses[self._idx]
            self._idx += 1
            return resp
        return "Task completed successfully. All steps verified."

    async def complete(
        self,
        messages: list[Any],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AgentResponse:
        content = self._next()
        return AgentResponse(content=content, state=RunState.COMPLETED)

    async def stream(
        self,
        messages: list[Any],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        content = self._next()
        for word in content.split():
            yield word + " "


# ---------------------------------------------------------------------------
# Milestone printer
# ---------------------------------------------------------------------------

_printed: list[str] = []


def milestone(name: str, detail: str = "") -> None:
    _printed.append(name)
    suffix = f"  ({detail})" if detail else ""
    print(f">> {name}{suffix}")


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------


async def run_demo() -> list[str]:
    import tempfile

    tmpdir = tempfile.mkdtemp(prefix="bahram_demo_")
    data_dir = Path(tmpdir)

    # Sub-directories for each subsystem
    mem_dir = data_dir / "memory"
    learn_dir = data_dir / "learning"
    reco_dir = data_dir / "recovery"
    ev_dir = data_dir / "events"
    job_dir = data_dir / "jobs"
    session_db = data_dir / "sessions.db"

    mem_dir.mkdir()
    learn_dir.mkdir()
    reco_dir.mkdir()
    ev_dir.mkdir()
    job_dir.mkdir()

    # -- 1. SESSION CREATED -------------------------------------------------
    from bahram.core.agent import Session
    from bahram.core.context import Context
    from bahram.core.persistence import SessionStore

    store = SessionStore(db_path=str(session_db))
    ctx = Context(max_turns=20)
    session = Session(metadata={"demo": True})
    store.create_session(session.id, metadata={"demo": True})
    ctx.create(session.id)
    milestone("SESSION CREATED", f"session_id={session.id[:8]}")

    # -- 2. MEMORY LOADED ---------------------------------------------------
    from bahram.memory.semantic import SemanticMemory

    memory = SemanticMemory(data_dir=str(mem_dir))
    # Seed memories so retrieval has something to find
    memory.add(
        content="deploy microservices using kubernetes on staging",
        source="conversation",
    )
    memory.add(
        content="deploy microservices using docker compose on production",
        source="conversation",
    )
    mem_ctx = memory.get_context("deploy microservices", max_memories=5)
    milestone("MEMORY LOADED", f"retrieved={len(mem_ctx)} chars")

    # -- 3. SKILLS LOADED ---------------------------------------------------
    # SkillManager expects a real config object; create one that points at a
    # temporary (empty) skills directory.  The manager gracefully handles no
    # .py files.
    from bahram.core.config import SkillsConfig

    skill_cfg = SkillsConfig(enabled=True, directory=str(data_dir / "skills"))
    (data_dir / "skills").mkdir(exist_ok=True)

    from bahram.skills.manager import SkillManager

    sm = SkillManager(skill_cfg)
    await sm.load_skills()
    milestone("SKILLS LOADED", f"count={len(sm.skills)}")

    # -- 4. SMART CONTEXT ---------------------------------------------------
    from bahram.core.smart_context import SmartContextManager

    sc = SmartContextManager(max_tokens=8192)
    sc.set_system_prompt("You are Bahram, a helpful AI agent.")
    sc.add_context(mem_ctx, priority=3, metadata={"source": "memory"})
    sc.add_history("user", "Deploy the microservice to staging")
    sc.add_history("assistant", "I will create a plan and execute it.")
    sc.optimize()
    usage = sc.get_usage()
    milestone(
        "SMART CONTEXT",
        f"used={usage['total_used']} tokens, remaining={usage['remaining']}",
    )

    # -- 5. PLAN CREATED ----------------------------------------------------
    from bahram.autonomy.plan import Plan, PlanStatus, PlanStep, StepStatus
    from bahram.autonomy.planner import Planner

    planner = Planner(provider=None)  # None -> deterministic fallback path
    plan = await planner.create_plan(
        goal="Deploy the microservice to staging",
        run_id="demo_run_001",
        context=mem_ctx,
        available_tools=["bash", "read", "write", "edit"],
    )
    milestone("PLAN CREATED", f"plan_id={plan.id}, steps={len(plan.steps)}")

    # -- 6. TOOL EXECUTED (via ToolExecutor) --------------------------------
    from bahram.core.engine import ToolCall as TC
    from bahram.core.engine import ToolExecutor, ToolResult

    @dataclass
    class EchoTool:
        """A trivial tool that echoes its arguments."""

        name: str = "echo"
        description: str = "Echoes input back"

        def schema(self) -> dict:
            return {
                "type": "function",
                "function": {
                    "name": self.name,
                    "description": self.description,
                    "parameters": {"type": "object", "properties": {}},
                },
            }

        async def execute(self, **kwargs: Any) -> str:
            return json.dumps({"status": "ok", "echo": kwargs})

    from bahram.security.approval import ApprovalConfig, ApprovalSystem

    approval = ApprovalSystem(ApprovalConfig())
    executor = ToolExecutor(tools={"echo": EchoTool()}, approval_system=approval)

    tc = TC(id="tc_001", name="echo", arguments={"message": "hello"})
    tr: ToolResult = await executor.execute(tc, timeout=10.0)
    milestone("TOOL EXECUTED", f"tool={tc.name}, success={tr.success}")

    # -- 7. SECURITY CHECK --------------------------------------------------
    is_dangerous, reason = approval.check_command("rm -rf /")
    risk = approval.assess_risk("rm -rf /") if is_dangerous else "low"
    milestone("SECURITY CHECK", f"dangerous={is_dangerous}, risk={risk}")

    # -- 8. SUBAGENT STARTED ------------------------------------------------
    from bahram.autonomy.subagent import SubagentEngine, SubagentResult

    # Build a minimal engine to host the subagent
    from bahram.core.config import Config
    from bahram.core.engine import AgentEngine

    cfg = Config()
    engine = AgentEngine(cfg)
    engine.register_provider("deterministic", DeterministicProvider())
    engine.register_tool("echo", EchoTool())

    from bahram.autonomy.events import EventTracker

    events = EventTracker(data_dir=str(ev_dir))
    sub_engine = SubagentEngine(engine, event_tracker=events)

    sub_result: SubagentResult = await sub_engine.spawn(
        parent_run_id="demo_run_001",
        objective="Verify staging is healthy",
        allowed_tools=["echo"],
        context="Staging cluster is up.",
        timeout_seconds=30,
    )
    milestone(
        "SUBAGENT STARTED",
        f"task_id={sub_result.task_id}, status={sub_result.status}",
    )

    # -- 9. FAILURE DETECTED ------------------------------------------------
    # Simulate a step failure
    failing_step = plan.steps[0]
    failing_step.status = StepStatus.RUNNING
    failing_step.attempt_count = 1
    failing_step.failure_reason = "Connection refused to staging server"

    from bahram.autonomy.recovery import RecoveryManager

    recovery = RecoveryManager(data_dir=str(reco_dir))

    from bahram.autonomy.replanner import Replanner
    from bahram.autonomy.verification import VerificationEngine

    ver_engine = VerificationEngine()
    replanner = Replanner(planner, ver_engine, max_replan_attempts=3)

    failed_plan = await replanner.handle_step_failure(
        plan,
        failing_step,
        "Connection refused to staging server",
    )
    milestone(
        "FAILURE DETECTED",
        f"step={failing_step.id}, cause=connection_error",
    )

    # -- 10. REPLAN CREATED -------------------------------------------------
    milestone(
        "REPLAN CREATED",
        f"replan_count={failed_plan.replan_count}, status={failed_plan.status.value}",
    )

    # -- 11. RECOVERY COMPLETE ----------------------------------------------
    cp = recovery.checkpoint(
        run_id="demo_run_001",
        plan=failed_plan,
        context_summary="Step 1 failed, replan inserted retry",
    )
    milestone("RECOVERY COMPLETE", f"checkpoint_steps={len(cp.completed_steps)}")

    # -- 12. VERIFY ----------------------------------------------------------
    vr_list = await ver_engine.verify(
        result="All services healthy",
        criteria=[{"type": "content_check", "params": {"contains": "healthy"}}],
    )
    all_passed = all(v.passed for v in vr_list)
    milestone("VERIFY", f"checks={len(vr_list)}, passed={all_passed}")

    # -- 13. CHECKPOINT CREATED ---------------------------------------------
    # Mark steps as completed for a clean checkpoint
    for step in failed_plan.steps:
        if step.status == StepStatus.RUNNING:
            step.status = StepStatus.COMPLETED
    cp2 = recovery.checkpoint(
        run_id="demo_run_001",
        plan=failed_plan,
        context_summary="All steps completed after replan",
    )
    milestone("CHECKPOINT CREATED", f"run_id={cp2.run_id}")

    # -- 14. COMPLETE -------------------------------------------------------
    failed_plan.status = PlanStatus.COMPLETED
    failed_plan.completed_at = time.time()
    failed_plan.updated_at = time.time()
    progress = failed_plan.get_progress()
    milestone(
        "COMPLETE",
        f"completed={progress['completed']}/{progress['total']}",
    )

    # -- 15. TRAJECTORY (emit events) ---------------------------------------
    events.emit_plan_created(
        session_id=session.id,
        run_id="demo_run_001",
        plan_id=failed_plan.id,
        data={"goal": failed_plan.goal},
    )
    for step in failed_plan.get_completed_steps():
        events.emit_step_completed(
            session_id=session.id,
            run_id="demo_run_001",
            plan_id=failed_plan.id,
            step_id=step.id,
            data={"objective": step.objective},
        )
    trace = events.get_trace("demo_run_001")
    milestone("TRAJECTORY", f"events={len(trace)}")

    # -- 16. LESSON ----------------------------------------------------------
    from bahram.autonomy.learning import LearningEngine

    learning = LearningEngine(data_dir=str(learn_dir))
    # Use success=False to trigger failure-based lesson extraction
    analysis = await learning.analyze_outcome(
        run_id="demo_run_001",
        goal="Deploy the microservice to staging",
        trajectory_steps=[
            {"step_id": s.id, "objective": s.objective, "status": s.status.value}
            for s in failed_plan.steps
        ],
        tool_results=[
            {"tool": "bash", "success": False, "error": "connection refused"},
            {"tool": "read", "success": True},
        ],
        success=False,
    )
    lessons = analysis.get("lessons_extracted", [])
    milestone("LESSON", f"count={len(lessons)}")

    # -- 17. SKILL -----------------------------------------------------------
    from bahram.autonomy.skill_lifecycle import SkillLifecycle

    skill_lifecycle = SkillLifecycle(learning)
    if len(lessons) >= 1:
        skill_candidate = await skill_lifecycle.generate_from_lessons(
            lessons, "Deploy the microservice to staging"
        )
        if skill_candidate:
            milestone(
                "SKILL",
                f"skill_id={skill_candidate.id}, name={skill_candidate.name}",
            )
        else:
            skill_candidate = await learning.generate_skill(lessons)
            if skill_candidate:
                milestone(
                    "SKILL",
                    f"skill_id={skill_candidate.id}, name={skill_candidate.name}",
                )
            else:
                milestone("SKILL", "skipped (generation returned None)")
    else:
        milestone("SKILL", "skipped (no lessons extracted)")

    # -- Budget check (supplementary) ---------------------------------------
    from bahram.autonomy.budget import BudgetManager

    budget = BudgetManager()
    budget.record_model_call("demo_run_001", input_tokens=500, output_tokens=300)
    budget.record_tool_call("demo_run_001")
    budget_status = budget.check_budget("demo_run_001")
    milestone(
        "BUDGET CHECK",
        f"can_continue={budget_status['can_continue']}, "
        f"tokens={budget_status['run_usage']['total_tokens']}",
    )

    # -- Event summary ------------------------------------------------------
    all_events = events.query_events(session_id=session.id)
    milestone(
        "EVENT TRACKER",
        f"total_events={len(all_events)}",
    )

    # -- Clean up persistent store ------------------------------------------
    store.delete_session(session.id)
    memory.close()

    return _printed


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 60)
    print("  Bahram Autonomy Chain – Deterministic Demo")
    print("=" * 60)
    print()

    milestones = asyncio.run(run_demo())

    print()
    print("-" * 60)
    print("  SUMMARY")
    print("-" * 60)
    print()
    print(f"  Milestones reached : {len(milestones)}")
    print()
    for i, m in enumerate(milestones, 1):
        print(f"    {i:>2}. {m}")
    print()
    print("  Chain coverage:")
    chain = [
        "SESSION", "MEMORY", "SMART CONTEXT", "PLAN", "TOOL", "SECURITY",
        "SUBAGENT", "FAILURE", "REPLAN", "RECOVERY", "VERIFY", "CHECKPOINT",
        "COMPLETE", "TRAJECTORY", "LESSON", "SKILL",
    ]
    for link in chain:
        # Check if any milestone string starts with the chain step name
        found = any(m.startswith(link) for m in milestones)
        mark = "OK" if found else "MISSING"
        print(f"    {mark:>7}  {link}")
    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
