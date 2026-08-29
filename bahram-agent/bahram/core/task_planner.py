"""Intelligent Task Planner for Bahram Agent."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TaskStep:
    """A step in a task plan."""

    id: str
    description: str
    dependencies: list[str] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, completed, failed
    result: Any = None


@dataclass
class TaskPlan:
    """A complete task plan."""

    id: str
    goal: str
    steps: list[TaskStep] = field(default_factory=list)
    status: str = "planning"
    created_at: float = 0.0


class TaskPlanner:
    """Intelligent task planning and decomposition."""

    def __init__(self) -> None:
        self._plans: dict[str, TaskPlan] = {}
        self._step_counter = 0

    async def create_plan(self, goal: str, context: dict = None) -> TaskPlan:
        """Create a plan from a goal."""
        import uuid
        import time

        plan_id = str(uuid.uuid4())[:8]
        plan = TaskPlan(
            id=plan_id,
            goal=goal,
            status="planning",
            created_at=time.time(),
        )

        # Analyze goal and create steps
        steps = await self._analyze_goal(goal, context)
        plan.steps = steps
        plan.status = "ready"

        self._plans[plan_id] = plan
        return plan

    async def _analyze_goal(self, goal: str, context: dict = None) -> list[TaskStep]:
        """Analyze goal and create steps."""
        steps = []

        # Simple heuristic - decompose based on common patterns
        goal_lower = goal.lower()

        if "create" in goal_lower or "build" in goal_lower:
            steps = await self._plan_creation(goal)
        elif "fix" in goal_lower or "debug" in goal_lower:
            steps = await self._plan_fix(goal)
        elif "test" in goal_lower:
            steps = await self._plan_testing(goal)
        elif "deploy" in goal_lower:
            steps = await self._plan_deployment(goal)
        else:
            steps = await self._plan_generic(goal)

        return steps

    async def _plan_creation(self, goal: str) -> list[TaskStep]:
        """Plan for creation tasks."""
        return [
            TaskStep(id="1", description="Understand requirements"),
            TaskStep(id="2", description="Design solution architecture"),
            TaskStep(id="3", description="Implement core functionality", dependencies=["2"]),
            TaskStep(id="4", description="Add tests", dependencies=["3"]),
            TaskStep(id="5", description="Review and refine", dependencies=["4"]),
        ]

    async def _plan_fix(self, goal: str) -> list[TaskStep]:
        """Plan for fix tasks."""
        return [
            TaskStep(id="1", description="Reproduce the issue"),
            TaskStep(id="2", description="Identify root cause"),
            TaskStep(id="3", description="Implement fix", dependencies=["2"]),
            TaskStep(id="4", description="Test fix", dependencies=["3"]),
        ]

    async def _plan_testing(self, goal: str) -> list[TaskStep]:
        """Plan for testing tasks."""
        return [
            TaskStep(id="1", description="Identify test cases"),
            TaskStep(id="2", description="Write test code"),
            TaskStep(id="3", description="Run tests"),
            TaskStep(id="4", description="Analyze results"),
        ]

    async def _plan_deployment(self, goal: str) -> list[TaskStep]:
        """Plan for deployment tasks."""
        return [
            TaskStep(id="1", description="Prepare deployment environment"),
            TaskStep(id="2", description="Configure deployment settings"),
            TaskStep(id="3", description="Deploy application"),
            TaskStep(id="4", description="Verify deployment"),
        ]

    async def _plan_generic(self, goal: str) -> list[TaskStep]:
        """Plan for generic tasks."""
        return [
            TaskStep(id="1", description="Analyze requirements"),
            TaskStep(id="2", description="Create implementation plan"),
            TaskStep(id="3", description="Execute plan", dependencies=["2"]),
            TaskStep(id="4", description="Verify results", dependencies=["3"]),
        ]

    def update_step(self, plan_id: str, step_id: str, status: str, result: Any = None) -> bool:
        """Update step status."""
        plan = self._plans.get(plan_id)
        if plan:
            for step in plan.steps:
                if step.id == step_id:
                    step.status = status
                    step.result = result
                    return True
        return False

    def get_plan(self, plan_id: str) -> Optional[dict]:
        """Get plan details."""
        plan = self._plans.get(plan_id)
        if plan:
            return {
                "id": plan.id,
                "goal": plan.goal,
                "status": plan.status,
                "steps": [
                    {
                        "id": s.id,
                        "description": s.description,
                        "status": s.status,
                        "dependencies": s.dependencies,
                    }
                    for s in plan.steps
                ],
            }
        return None

    def get_next_step(self, plan_id: str) -> Optional[TaskStep]:
        """Get next step to execute."""
        plan = self._plans.get(plan_id)
        if plan:
            for step in plan.steps:
                if step.status == "pending":
                    # Check if dependencies are met
                    deps_met = all(
                        any(s.id == dep and s.status == "completed" for s in plan.steps)
                        for dep in step.dependencies
                    )
                    if deps_met:
                        return step
        return None

    def get_progress(self, plan_id: str) -> dict[str, Any]:
        """Get plan progress."""
        plan = self._plans.get(plan_id)
        if plan:
            total = len(plan.steps)
            completed = sum(1 for s in plan.steps if s.status == "completed")
            return {
                "total": total,
                "completed": completed,
                "progress": completed / total * 100 if total > 0 else 0,
            }
        return {"total": 0, "completed": 0, "progress": 0}
