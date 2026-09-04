"""
Plan.

Public objects: ``PlanStatus``, ``StepStatus``, ``PlanStep``, ``Plan``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PlanStatus(str, Enum):
    """
    Plan status.
    """

    CREATED = "created"
    PLANNING = "planning"
    READY = "ready"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    REPLANNING = "replanning"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    """
    Step status.
    """

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    REPLANNED = "replanned"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class PlanStep:
    """
    Plan step.

    Attributes:
        id (str): id string.
        plan_id (str): plan identifier.
        objective (str): objective string.
        dependencies (list[str]): collection of dependencies.
        required_tools (list[str]): collection of required tools.
        required_capabilities (list[str]): collection of required capabilities.
        status (StepStatus): status.
        attempt_count (int): numeric value for attempt count.
        max_attempts (int): numeric value for max attempts.
        result (str | None): result string.
        verification_criteria (list[dict[str, Any]]): collection of verification criteria.
        verification_result (str | None): verification result string.
        failure_reason (str | None): failure reason string.
        tool_calls (list[dict[str, Any]]): collection of tool calls.
        created_at (float): numeric value for created at.
        updated_at (float): numeric value for updated at.
        started_at (float | None): numeric value for started at.
        completed_at (float | None): numeric value for completed at.
        delegated_to (str | None): delegated to string.
        metadata (dict[str, Any]): mapping of metadata.
    """

    id: str
    plan_id: str
    objective: str
    dependencies: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    required_capabilities: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    attempt_count: int = 0
    max_attempts: int = 3
    result: str | None = None
    verification_criteria: list[dict[str, Any]] = field(default_factory=list)
    verification_result: str | None = None
    failure_reason: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    delegated_to: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """
        Serialise the object to a JSON-serialisable dictionary.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "objective": self.objective,
            "dependencies": self.dependencies,
            "required_tools": self.required_tools,
            "required_capabilities": self.required_capabilities,
            "status": self.status.value,
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "result": self.result,
            "verification_criteria": self.verification_criteria,
            "verification_result": self.verification_result,
            "failure_reason": self.failure_reason,
            "tool_calls": self.tool_calls,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "delegated_to": self.delegated_to,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanStep:
        """
        Build an instance from dict.

        Args:
            data (dict[str, Any]): mapping of data.

        Returns:
            PlanStep: the resulting PlanStep.
        """
        data["status"] = StepStatus(data["status"])
        return cls(**data)


@dataclass
class Plan:
    """
    Plan.

    Attributes:
        id (str): id string.
        run_id (str): run identifier.
        goal (str): goal string.
        strategy (str): strategy string.
        rationale (str): rationale string.
        status (PlanStatus): status.
        success_criteria (list[str]): collection of success criteria.
        risk_assessment (str): risk assessment string.
        steps (list[PlanStep]): collection of steps.
        created_at (float): numeric value for created at.
        updated_at (float): numeric value for updated at.
        completed_at (float | None): numeric value for completed at.
        replan_count (int): numeric value for replan count.
        metadata (dict[str, Any]): mapping of metadata.
    """

    id: str
    run_id: str
    goal: str
    strategy: str = ""
    rationale: str = ""
    status: PlanStatus = PlanStatus.CREATED
    success_criteria: list[str] = field(default_factory=list)
    risk_assessment: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    replan_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """
        Serialise the object to a JSON-serialisable dictionary.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {
            "id": self.id,
            "run_id": self.run_id,
            "goal": self.goal,
            "strategy": self.strategy,
            "rationale": self.rationale,
            "status": self.status.value,
            "success_criteria": self.success_criteria,
            "risk_assessment": self.risk_assessment,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "replan_count": self.replan_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Plan:
        """
        Build an instance from dict.

        Args:
            data (dict[str, Any]): mapping of data.

        Returns:
            Plan: the resulting Plan.
        """
        data["status"] = PlanStatus(data["status"])
        data["steps"] = [PlanStep.from_dict(s) for s in data.get("steps", [])]
        return cls(**data)

    def get_step(self, step_id: str) -> PlanStep | None:
        """
        Return the step.

        Args:
            step_id (str): plan-step identifier.

        Returns:
            PlanStep | None: the resulting object, or ``None`` when it is not available.
        """
        for s in self.steps:
            if s.id == step_id:
                return s
        return None

    def get_ready_steps(self) -> list[PlanStep]:
        """
        Return the ready steps.

        Returns:
            list[PlanStep]: a sequence of PlanStep entries (empty when there is nothing to report).
        """
        ready = []
        for step in self.steps:
            if step.status != StepStatus.PENDING:
                continue
            deps_met = all(
                any(s.id == dep and s.status == StepStatus.COMPLETED for s in self.steps)
                for dep in step.dependencies
            )
            if deps_met:
                ready.append(step)
        return ready

    def get_completed_steps(self) -> list[PlanStep]:
        """
        Return the completed steps.

        Returns:
            list[PlanStep]: a sequence of PlanStep entries (empty when there is nothing to report).
        """
        return [s for s in self.steps if s.status == StepStatus.COMPLETED]

    def get_failed_steps(self) -> list[PlanStep]:
        """
        Return the failed steps.

        Returns:
            list[PlanStep]: a sequence of PlanStep entries (empty when there is nothing to report).
        """
        return [s for s in self.steps if s.status == StepStatus.FAILED]

    def is_complete(self) -> bool:
        """
        Return ``True`` when complete.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        return all(
            s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED, StepStatus.CANCELLED)
            for s in self.steps
        )

    def has_failures(self) -> bool:
        """
        Return ``True`` when the object has failures.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        return any(s.status == StepStatus.FAILED for s in self.steps)

    def get_progress(self) -> dict[str, Any]:
        """
        Return the progress.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        total = len(self.steps)
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        failed = sum(1 for s in self.steps if s.status == StepStatus.FAILED)
        running = sum(1 for s in self.steps if s.status == StepStatus.RUNNING)
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": total - completed - failed - running,
            "progress_pct": (completed / total * 100) if total > 0 else 0,
        }

    def detect_cycles(self) -> list[list[str]] | None:
        """Detect cycles in the dependency DAG. Returns cycle paths if found, None otherwise."""
        adjacency: dict[str, list[str]] = {}
        for step in self.steps:
            adjacency[step.id] = step.dependencies[:]

        visited: set[str] = set()
        rec_stack: set[str] = set()
        cycles: list[list[str]] = []

        def dfs(node: str, path: list[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path):
                        return True
                elif neighbor in rec_stack:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                    return True
            path.pop()
            rec_stack.discard(node)
            return False

        for step_id in adjacency:
            if step_id not in visited:
                dfs(step_id, [])

        return cycles if cycles else None

    def validate_dependencies(self) -> list[str]:
        """Validate all dependencies reference existing steps. Returns error messages."""
        step_ids = {s.id for s in self.steps}
        errors = []
        for step in self.steps:
            for dep in step.dependencies:
                if dep not in step_ids:
                    errors.append(f"Step '{step.id}' depends on non-existent step '{dep}'")
        return errors

    def add_step(self, step: PlanStep) -> None:
        """
        Add step.

        Args:
            step (PlanStep): step.
        """
        self.steps.append(step)
        self.updated_at = time.time()

    def remove_step(self, step_id: str) -> bool:
        """
        Remove step.

        Args:
            step_id (str): plan-step identifier.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        original_len = len(self.steps)
        self.steps = [s for s in self.steps if s.id != step_id]
        if len(self.steps) < original_len:
            for s in self.steps:
                s.dependencies = [d for d in s.dependencies if d != step_id]
            self.updated_at = time.time()
            return True
        return False

    def insert_step_after(self, after_id: str, step: PlanStep) -> bool:
        """
        Insert step after.

        Args:
            after_id (str): after id string.
            step (PlanStep): step.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        for i, s in enumerate(self.steps):
            if s.id == after_id:
                step.dependencies = list(set(step.dependencies + [after_id]))
                self.steps.insert(i + 1, step)
                for s2 in self.steps:
                    if after_id in s2.dependencies and s2.id != step.id:
                        s2.dependencies.append(step.id)
                self.updated_at = time.time()
                return True
        return False
