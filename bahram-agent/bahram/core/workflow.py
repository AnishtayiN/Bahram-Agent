"""
Workflow.

Public objects: ``WorkflowStep``, ``Workflow``, ``WorkflowAutomation``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class WorkflowStep:
    """
    Workflow step.

    Attributes:
        id (str): id string.
        name (str): name of the object.
        action (str): action string.
        params (dict): mapping of params.
        dependencies (list[str]): collection of dependencies.
        status (str): status string.
        result (Any): result.
    """

    id: str
    name: str
    action: str
    params: dict = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    status: str = "pending"
    result: Any = None


@dataclass
class Workflow:
    """
    Workflow.

    Attributes:
        id (str): id string.
        name (str): name of the object.
        steps (list[WorkflowStep]): collection of steps.
        status (str): status string.
        current_step (int): numeric value for current step.
    """

    id: str
    name: str
    steps: list[WorkflowStep] = field(default_factory=list)
    status: str = "idle"
    current_step: int = 0


class WorkflowAutomation:
    """
    Workflow automation.
    """

    def __init__(self) -> None:
        """
        Initialise a WorkflowAutomation instance.
        """
        self._workflows: dict[str, Workflow] = {}
        self._actions: dict[str, Callable] = {}
        self._history: list[dict] = []

    def register_action(self, name: str, action: Callable) -> None:
        """
        Register action.

        Args:
            name (str): name of the object.
            action (Callable): callable used for action.
        """
        self._actions[name] = action

    def create_workflow(self, name: str, steps: list[dict]) -> Workflow:
        """
        Create workflow.

        Args:
            name (str): name of the object.
            steps (list[dict]): collection of steps.

        Returns:
            Workflow: the resulting Workflow.
        """
        import uuid

        workflow_id = str(uuid.uuid4())[:8]
        workflow_steps = [
            WorkflowStep(
                id=str(i + 1),
                name=step.get("name", f"Step {i + 1}"),
                action=step.get("action", ""),
                params=step.get("params", {}),
                dependencies=step.get("dependencies", []),
            )
            for i, step in enumerate(steps)
        ]

        workflow = Workflow(
            id=workflow_id,
            name=name,
            steps=workflow_steps,
        )
        self._workflows[workflow_id] = workflow
        return workflow

    async def execute(self, workflow_id: str) -> dict[str, Any]:
        """
        Execute the tool and return its textual result.

        Args:
            workflow_id (str): workflow id string.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return {"error": f"Workflow '{workflow_id}' not found"}

        workflow.status = "running"
        results = []

        for step in workflow.steps:
            deps_met = all(
                any(s.id == dep and s.status == "completed" for s in workflow.steps)
                for dep in step.dependencies
            )

            if not deps_met:
                continue

            step.status = "running"
            try:
                action = self._actions.get(step.action)
                if action:
                    if asyncio.iscoroutinefunction(action):
                        result = await action(**step.params)
                    else:
                        result = action(**step.params)
                    step.result = result
                    step.status = "completed"
                    results.append(
                        {"step": step.name, "status": "success", "result": str(result)[:200]}
                    )
                else:
                    step.status = "failed"
                    results.append(
                        {"step": step.name, "status": "failed", "error": "Action not found"}
                    )
            except Exception as e:
                logger.error("Workflow step %s failed: %s", step.name, e, exc_info=True)
                step.status = "failed"
                results.append({"step": step.name, "status": "failed", "error": str(e)})

        workflow.status = "completed"
        self._history.append(
            {
                "workflow_id": workflow_id,
                "name": workflow.name,
                "results": results,
            }
        )

        return {"status": "completed", "results": results}

    def get_workflow(self, workflow_id: str) -> dict | None:
        """
        Return the workflow.

        Args:
            workflow_id (str): workflow id string.

        Returns:
            dict | None: a mapping of str, Any.
        """
        workflow = self._workflows.get(workflow_id)
        if workflow:
            return {
                "id": workflow.id,
                "name": workflow.name,
                "status": workflow.status,
                "steps": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "status": s.status,
                        "result": str(s.result)[:100] if s.result else None,
                    }
                    for s in workflow.steps
                ],
            }
        return None

    def get_progress(self, workflow_id: str) -> dict[str, Any]:
        """
        Return the progress.

        Args:
            workflow_id (str): workflow id string.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        workflow = self._workflows.get(workflow_id)
        if workflow:
            total = len(workflow.steps)
            completed = sum(1 for s in workflow.steps if s.status == "completed")
            return {
                "total": total,
                "completed": completed,
                "progress": completed / total * 100 if total > 0 else 0,
            }
        return {"total": 0, "completed": 0, "progress": 0}

    def list_workflows(self) -> list[dict]:
        """
        List workflows.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        return [
            {
                "id": w.id,
                "name": w.name,
                "status": w.status,
                "steps": len(w.steps),
            }
            for w in self._workflows.values()
        ]

    def get_history(self) -> list[dict]:
        """
        Return the history.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        return self._history.copy()
