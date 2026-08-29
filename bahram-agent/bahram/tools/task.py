from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

@dataclass
class Task:
    ""

    task_id: str
    name: str
    status: str = "pending"
    result: Any = None
    error: str = ""
    start_time: float = 0.0
    end_time: float = 0.0

class TaskTool:
    ""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._callbacks: dict[str, Callable] = {}

    async def launch(
        self,
        task_id: str,
        name: str,
        func: Callable,
        *args,
        **kwargs,
    ) -> Task:
        ""
        import time

        task = Task(
            task_id=task_id,
            name=name,
            status="running",
            start_time=time.time(),
        )
        self._tasks[task_id] = task

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            task.status = "completed"
            task.result = result
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            logger.warning(f"Task {task_id} failed: {e}")

        task.end_time = time.time()

        if task_id in self._callbacks:
            try:
                await self._callbacks[task_id](task)
            except Exception as e:
                logger.warning(f"Task callback failed: {e}")

        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        ""
        return self._tasks.get(task_id)

    def get_status(self, task_id: str) -> str:
        ""
        task = self._tasks.get(task_id)
        return task.status if task else "not_found"

    def get_result(self, task_id: str) -> Any:
        ""
        task = self._tasks.get(task_id)
        if task and task.status == "completed":
            return task.result
        return None

    def set_callback(self, task_id: str, callback: Callable) -> None:
        ""
        self._callbacks[task_id] = callback

    def list_tasks(self) -> list[dict]:
        ""
        return [
            {
                "id": t.task_id,
                "name": t.name,
                "status": t.status,
                "duration": t.end_time - t.start_time if t.end_time else 0,
            }
            for t in self._tasks.values()
        ]

    def cancel(self, task_id: str) -> bool:
        ""
        task = self._tasks.get(task_id)
        if task and task.status == "running":
            task.status = "cancelled"
            return True
        return False
