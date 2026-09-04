from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class DelegatedTask:

    task_id: str
    agent: str
    description: str
    status: str = "pending"
    result: Any = None
    error: str = ""

class DelegationTool:

    def __init__(self) -> None:
        self._agents: dict[str, Callable] = {}
        self._tasks: dict[str, DelegatedTask] = {}

    def register_agent(self, name: str, handler: Callable) -> None:
        self._agents[name] = handler

    async def delegate(
        self,
        agent: str,
        task_id: str,
        description: str,
        **kwargs,
    ) -> dict[str, Any]:
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
        return list(self._agents.keys())

    def list_tasks(self) -> list[dict]:
        return [
            {
                "task_id": t.task_id,
                "agent": t.agent,
                "status": t.status,
            }
            for t in self._tasks.values()
        ]
