"""
Delegation.

Public objects: ``DelegatedTask``, ``DelegationTool``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DelegatedTask:
    """
    Delegated task.

    Attributes:
        task_id (str): task identifier.
        agent (str): agent string.
        description (str): human readable description.
        status (str): status string.
        result (Any): result.
        error (str): error string.
    """

    task_id: str
    agent: str
    description: str
    status: str = "pending"
    result: Any = None
    error: str = ""


class DelegationTool:
    """
    Delegation tool.
    """

    def __init__(self) -> None:
        """
        Initialise a DelegationTool instance.
        """
        self._agents: dict[str, Callable] = {}
        self._tasks: dict[str, DelegatedTask] = {}

    def register_agent(self, name: str, handler: Callable) -> None:
        """
        Register agent.

        Args:
            name (str): name of the object.
            handler (Callable): callable used for handler.
        """
        self._agents[name] = handler

    async def delegate(
        self,
        agent: str,
        task_id: str,
        description: str,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Delegate.

        Args:
            agent (str): agent string.
            task_id (str): task identifier.
            description (str): human readable description.
            **kwargs: keyword arguments forwarded to the implementation.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        if agent not in self._agents:
            return {"error": f"Agent '{agent}' not registered"}

        task = DelegatedTask(
            task_id=task_id,
            agent=agent,
            description=description,
            status="running",
        )
        self._tasks[task_id] = task

        try:
            handler = self._agents[agent]
            if asyncio.iscoroutinefunction(handler):
                result = await handler(task_id=task_id, description=description, **kwargs)
            else:
                result = handler(task_id=task_id, description=description, **kwargs)

            task.status = "completed"
            task.result = result
            return {"status": "completed", "result": result}

        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            return {"status": "failed", "error": str(e)}

    def get_task(self, task_id: str) -> dict | None:
        """
        Return the task.

        Args:
            task_id (str): task identifier.

        Returns:
            dict | None: a mapping of str, Any.
        """
        task = self._tasks.get(task_id)
        if task:
            return {
                "task_id": task.task_id,
                "agent": task.agent,
                "description": task.description,
                "status": task.status,
                "result": task.result,
                "error": task.error,
            }
        return None

    def list_agents(self) -> list[str]:
        """
        List agents.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        return list(self._agents.keys())

    def list_tasks(self) -> list[dict]:
        """
        List tasks.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        return [
            {
                "task_id": t.task_id,
                "agent": t.agent,
                "status": t.status,
            }
            for t in self._tasks.values()
        ]
