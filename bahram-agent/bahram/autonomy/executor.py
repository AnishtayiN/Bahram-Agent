from __future__ import annotations

import logging
from typing import Any, Protocol

from bahram.autonomy.budget import BudgetConfig, BudgetManager
from bahram.autonomy.events import EventTracker
from bahram.autonomy.plan import Plan, PlanStatus, PlanStep, StepStatus
from bahram.autonomy.replanner import Replanner
from bahram.autonomy.verification import VerificationEngine, VerificationResult

logger = logging.getLogger(__name__)


class LLMProviderForExecutor(Protocol):
    async def complete(
        self, messages: list[Any], tools: list[dict[str, Any]] | None = None, **kwargs: Any
    ) -> Any: ...


class PlanExecutor:
    def __init__(
        self,
        engine: Any,
        planner: Any,
        verification_engine: VerificationEngine,
        replanner: Replanner,
        budget_manager: BudgetManager | None = None,
        event_tracker: EventTracker | None = None,
        recovery_manager: Any = None,
    ) -> None:
        self._engine = engine
        self._planner = planner
        self._verification_engine = verification_engine
        self._replanner = replanner
        self._budget_manager = budget_manager
        self._event_tracker = event_tracker
        self._recovery_manager = recovery_manager

    async def execute_plan(
        self,
        plan: Plan,
        messages: list[Any],
        model: str | None = None,
        session_id: str = "",
        run_id: str = "",
    ) -> Plan:
        plan.status = PlanStatus.EXECUTING
        plan.updated_at = time.time()

        if self._event_tracker:
            self._event_tracker.emit_plan_created(
                session_id=session_id, run_id=run_id, plan_id=plan.id,
                data={"goal": plan.goal, "steps": len(plan.steps)},
            )

        while not plan.is_complete() and plan.status == PlanStatus.EXECUTING:
            ready_steps = plan.get_ready_steps()
            if not ready_steps:
                if plan.has_failures():
                    plan.status = PlanStatus.FAILED
                else:
                    all_done = all(
                        s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED, StepStatus.CANCELLED, StepStatus.FAILED)
                        for s in plan.steps
                    )
                    if all_done:
                        plan.status = PlanStatus.COMPLETED
                break

            for step in ready_steps:
                if plan.status != PlanStatus.EXECUTING:
                    break

                step.status = StepStatus.RUNNING
                step.started_at = time.time()
                step.attempt_count += 1

                if self._event_tracker:
                    self._event_tracker.emit_step_started(
                        session_id=session_id, run_id=run_id,
                        plan_id=plan.id, step_id=step.id,
                        data={"objective": step.objective, "attempt": step.attempt_count},
                    )

                try:
                    result = await self._execute_step(step, messages, model, run_id)

                    if result.get("success", False):
                        step.result = result.get("output", "")
                        step.tool_calls = result.get("tool_calls", [])

                        if step.verification_criteria:
                            vr = await self._verification_engine.verify(
                                step.result, step.verification_criteria
                            )
                            all_passed = all(r.passed for r in vr)
                            if all_passed:
                                step.status = StepStatus.COMPLETED
                                step.verification_result = "passed"
                            else:
                                step.status = StepStatus.FAILED
                                step.failure_reason = "; ".join(r.details for r in vr if not r.passed)
                                step.verification_result = "failed"
                        else:
                            step.status = StepStatus.COMPLETED
                    else:
                        step.status = StepStatus.FAILED
                        step.failure_reason = result.get("error", "Unknown error")

                except Exception as e:
                    step.status = StepStatus.FAILED
                    step.failure_reason = str(e)

                step.completed_at = time.time()
                step.updated_at = time.time()

                if self._event_tracker:
                    event_fn = (
                        self._event_tracker.emit_step_completed
                        if step.status == StepStatus.COMPLETED
                        else self._event_tracker.emit_step_failed
                    )
                    event_fn(
                        session_id=session_id, run_id=run_id,
                        plan_id=plan.id, step_id=step.id,
                        data={"status": step.status.value, "error": step.failure_reason},
                    )

                if step.status == StepStatus.COMPLETED and self._recovery_manager is not None:
                    try:
                        self._recovery_manager.checkpoint(
                            run_id=run_id, plan=plan,
                            context_summary=f"Step {step.id} completed: {step.objective[:100]}",
                        )
                    except Exception as e:
                        logger.warning(f"Auto-checkpoint failed: {e}")

                if step.status == StepStatus.FAILED:
                    plan = await self._replanner.handle_step_failure(
                        plan, step, step.failure_reason or "Unknown error",
                        step.result or "",
                    )

                    if plan.status == PlanStatus.REPLANNING:
                        if self._event_tracker:
                            self._event_tracker.emit_replanned(
                                session_id=session_id, run_id=run_id, plan_id=plan.id,
                                data={"replan_count": plan.replan_count},
                            )
                        plan.status = PlanStatus.EXECUTING
                        break

                    if plan.status == PlanStatus.FAILED:
                        break

        if plan.is_complete() and plan.status == PlanStatus.EXECUTING:
            plan.status = PlanStatus.COMPLETED
        plan.completed_at = time.time()
        plan.updated_at = time.time()

        return plan

    async def _execute_step(
        self,
        step: PlanStep,
        messages: list[Any],
        model: str | None,
        run_id: str,
    ) -> dict[str, Any]:
        step_context = (
            f"Execute this specific step: {step.objective}\n"
            f"Required tools: {', '.join(step.required_tools) if step.required_tools else 'any'}\n"
        )
        if step.result:
            step_context += f"Previous step result: {step.result[:500]}\n"

        from bahram.core.engine import Message, MessageRole

        step_messages = list(messages) + [
            Message(role=MessageRole.USER, content=step_context),
        ]

        provider = self._engine.get_provider(
            model or (self._engine.config.agent.model if self._engine.config else "anthropic/claude-sonnet-4-20250514")
        )

        tools_schema = self._engine.get_tools_schema()
        if step.required_tools:
            tools_schema = [
                t for t in tools_schema
                if t.get("function", {}).get("name", "") in step.required_tools
            ]

        tool_calls_data = []
        total_tool_calls = 0

        for iteration in range(10):
            try:
                response = await provider.complete(
                    step_messages, tools_schema if tools_schema else None
                )
            except Exception as e:
                return {"success": False, "error": f"Provider error: {e}", "tool_calls": []}

            if not response.tool_calls:
                return {
                    "success": True,
                    "output": response.content or "",
                    "tool_calls": tool_calls_data,
                }

            for tool_call in response.tool_calls:
                if total_tool_calls >= 20:
                    break

                executor = self._engine._tool_executor
                if executor is None:
                    from bahram.core.engine import ToolExecutor
                    executor = ToolExecutor(self._engine.tools, self._engine._approval_system)

                result = await executor.execute(tool_call, timeout=60.0)
                total_tool_calls += 1

                if self._budget_manager:
                    self._budget_manager.record_tool_call(run_id)

                tool_calls_data.append({
                    "tool": tool_call.name,
                    "success": result.success,
                })

                step_messages.append(Message(
                    role=MessageRole.TOOL,
                    content=result.content if result.success else f"Error: {result.error}",
                    tool_call_id=result.tool_call_id,
                ))

            step_messages.append(Message(
                role=MessageRole.ASSISTANT,
                content=response.content or "",
                metadata={"tool_calls": response.tool_calls} if response.tool_calls else {},
            ))

        return {
            "success": False,
            "error": "Max iterations reached in step execution",
            "tool_calls": tool_calls_data,
        }


import time
