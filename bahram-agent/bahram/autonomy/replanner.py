"""
Replanner.

Public objects: ``ReplanningStrategy``, ``Deviation``, ``Replanner``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from bahram.autonomy.plan import Plan, PlanStatus, PlanStep, StepStatus
from bahram.autonomy.planner import Planner
from bahram.autonomy.verification import VerificationEngine, VerificationResult

logger = logging.getLogger(__name__)


class ReplanningStrategy:
    """
    Replanning strategy.
    """

    RETRY = "retry"
    MODIFY_STEP = "modify_step"
    INSERT_STEP = "insert_step"
    REORDER = "reorder"
    REPLAN = "replan"
    SKIP = "skip"
    ABORT = "abort"


@dataclass
class Deviation:
    """
    Deviation.

    Attributes:
        step_id (str): plan-step identifier.
        error (str): error string.
        cause (str): cause string.
        strategy (str): strategy string.
        timestamp (float): numeric value for timestamp.
        metadata (dict[str, Any]): mapping of metadata.
    """

    step_id: str
    error: str
    cause: str
    strategy: str
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class Replanner:
    """
    Replanner.
    """

    def __init__(
        self,
        planner: Planner,
        verification_engine: VerificationEngine,
        max_replan_attempts: int = 3,
    ) -> None:
        """
        Initialise a Replanner instance.

        Args:
            planner (Planner): planner.
            verification_engine (VerificationEngine): verification engine.
            max_replan_attempts (int): numeric value for max replan attempts. Defaults to ``3``.
        """
        self._planner = planner
        self._verification_engine = verification_engine
        self._max_replan_attempts = max_replan_attempts
        self._deviations: list[Deviation] = []

    async def handle_step_failure(
        self,
        plan: Plan,
        step: PlanStep,
        error: str,
        tool_result: str = "",
    ) -> Plan:
        """
        Handle step failure.

        Args:
            plan (Plan): plan.
            step (PlanStep): step.
            error (str): error string.
            tool_result (str): tool result string. Defaults to ``''``.

        Returns:
            Plan: the resulting Plan.

        Note:
            Coroutine - must be awaited.
        """
        deviation = self._classify_failure(step, error, tool_result)
        self._deviations.append(deviation)

        logger.info(
            f"Step '{step.id}' failed. Cause: {deviation.cause}. Strategy: {deviation.strategy}"
        )

        if deviation.strategy == ReplanningStrategy.RETRY:
            return self._handle_retry(plan, step)
        elif deviation.strategy == ReplanningStrategy.MODIFY_STEP:
            return self._handle_modify(plan, step, error)
        elif deviation.strategy == ReplanningStrategy.INSERT_STEP:
            return await self._handle_insert(plan, step, error)
        elif deviation.strategy == ReplanningStrategy.SKIP:
            return self._handle_skip(plan, step)
        elif deviation.strategy == ReplanningStrategy.REPLAN:
            return await self._handle_full_replan(plan, step, error)
        elif deviation.strategy == ReplanningStrategy.ABORT:
            return self._handle_abort(plan, step, error)
        else:
            return self._handle_retry(plan, step)

    async def handle_verification_failure(
        self,
        plan: Plan,
        step: PlanStep,
        results: list[VerificationResult],
    ) -> Plan:
        """
        Handle verification failure.

        Args:
            plan (Plan): plan.
            step (PlanStep): step.
            results (list[VerificationResult]): collection of results.

        Returns:
            Plan: the resulting Plan.

        Note:
            Coroutine - must be awaited.
        """
        failed = [r for r in results if not r.passed]
        if not failed:
            return plan

        error_summary = "; ".join(r.details for r in failed)

        if step.attempt_count < step.max_attempts:
            logger.info(
                f"Verification failed for step '{step.id}', retrying "
                f"(attempt {step.attempt_count + 1}/{step.max_attempts})"
            )
            return self._handle_retry(plan, step)

        return await self._handle_full_replan(plan, step, error_summary)

    def _classify_failure(self, step: PlanStep, error: str, tool_result: str) -> Deviation:
        error_lower = error.lower()

        if any(kw in error_lower for kw in ("timeout", "timed out", "deadline")):
            cause = "timeout"
            strategy = ReplanningStrategy.RETRY
        elif any(kw in error_lower for kw in ("permission", "denied", "forbidden", "access")):
            cause = "permission_denial"
            strategy = ReplanningStrategy.MODIFY_STEP
        elif any(kw in error_lower for kw in ("not found", "no such file", "does not exist")):
            cause = "missing_resource"
            strategy = ReplanningStrategy.INSERT_STEP
        elif any(kw in error_lower for kw in ("syntax", "invalid", "parse", "format")):
            cause = "invalid_output"
            strategy = ReplanningStrategy.MODIFY_STEP
        elif any(kw in error_lower for kw in ("connection", "network", "dns", "refused")):
            cause = "network_error"
            strategy = ReplanningStrategy.RETRY
        elif any(kw in error_lower for kw in ("budget", "limit", "exceeded", "quota")):
            cause = "resource_exhaustion"
            strategy = ReplanningStrategy.ABORT
        elif step.attempt_count >= step.max_attempts:
            cause = "max_retries_exceeded"
            strategy = ReplanningStrategy.REPLAN
        else:
            cause = "tool_error"
            if step.attempt_count < 2:
                strategy = ReplanningStrategy.RETRY
            else:
                strategy = ReplanningStrategy.REPLAN

        return Deviation(
            step_id=step.id,
            error=error,
            cause=cause,
            strategy=strategy,
        )

    def _handle_retry(self, plan: Plan, step: PlanStep) -> Plan:
        step.status = StepStatus.PENDING
        step.attempt_count += 1
        step.failure_reason = None
        step.updated_at = time.time()
        return plan

    def _handle_modify(self, plan: Plan, step: PlanStep, error: str) -> Plan:
        step.status = StepStatus.REPLANNED
        step.updated_at = time.time()

        modified_step = PlanStep(
            id=f"{step.id}_modified",
            plan_id=plan.id,
            objective=f"Modified: {step.objective}",
            dependencies=step.dependencies[:],
            required_tools=step.required_tools[:],
            required_capabilities=step.required_capabilities[:],
            verification_criteria=step.verification_criteria[:],
            metadata={"modified_from": step.id, "original_error": error},
        )
        plan.insert_step_after(step.id, modified_step)
        return plan

    async def _handle_insert(self, plan: Plan, step: PlanStep, error: str) -> Plan:
        step.status = StepStatus.WAITING
        step.updated_at = time.time()

        prereq_step = PlanStep(
            id=f"{step.id}_prereq",
            plan_id=plan.id,
            objective=f"Prepare prerequisite for: {step.objective}",
            dependencies=step.dependencies[:],
            required_tools=["read", "bash"],
            metadata={"inserted_for": step.id, "reason": error},
        )
        step.dependencies = [prereq_step.id]
        plan.insert_step_after(step.id, prereq_step)

        idx = next(i for i, s in enumerate(plan.steps) if s.id == prereq_step.id)
        plan.steps.insert(0, plan.steps.pop(idx))

        return plan

    def _handle_skip(self, plan: Plan, step: PlanStep) -> Plan:
        step.status = StepStatus.SKIPPED
        step.updated_at = time.time()
        return plan

    async def _handle_full_replan(self, plan: Plan, step: PlanStep, error: str) -> Plan:
        if plan.replan_count >= self._max_replan_attempts:
            logger.warning(
                f"Max replan attempts ({self._max_replan_attempts}) reached for plan '{plan.id}'"
            )
            return self._handle_abort(plan, step, error)

        plan.status = PlanStatus.REPLANNING
        plan = await self._planner.replan(plan, step, error)
        plan.status = PlanStatus.EXECUTING
        return plan

    def _handle_abort(self, plan: Plan, step: PlanStep, error: str) -> Plan:
        step.status = StepStatus.FAILED
        step.failure_reason = error
        step.updated_at = time.time()

        for s in plan.steps:
            if s.status == StepStatus.PENDING:
                s.status = StepStatus.CANCELLED

        plan.status = PlanStatus.FAILED
        plan.updated_at = time.time()
        return plan

    def get_deviations(self) -> list[Deviation]:
        """
        Return the deviations.

        Returns:
            list[Deviation]: a sequence of Deviation entries (empty when there is nothing to
                report).
        """
        return self._deviations[:]
