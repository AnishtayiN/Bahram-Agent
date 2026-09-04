"""
Bg notify.

Public objects: ``BackgroundTask``, ``BackgroundNotifier``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BackgroundTask:
    """
    Background task.

    Attributes:
        task_id (str): task identifier.
        name (str): name of the object.
        status (str): status string.
        result (Any): result.
        error (str): error string.
        start_time (float): numeric value for start time.
        end_time (float): numeric value for end time.
        notify_chat_id (str): notify chat id string.
        notify_platform (str): notify platform string.
    """

    task_id: str
    name: str
    status: str = "pending"
    result: Any = None
    error: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    notify_chat_id: str = ""
    notify_platform: str = ""


class BackgroundNotifier:
    """
    Background notifier.
    """

    def __init__(self) -> None:
        """
        Initialise a BackgroundNotifier instance.
        """
        self._tasks: dict[str, BackgroundTask] = {}
        self._notify_fn: Callable | None = None

    def set_notify_function(self, fn: Callable) -> None:
        """
        Set the notify function.

        Args:
            fn (Callable): callable used for fn.
        """
        self._notify_fn = fn

    def start_task(
        self,
        task_id: str,
        name: str,
        notify_chat_id: str = "",
        notify_platform: str = "",
    ) -> None:
        """
        Start task.

        Args:
            task_id (str): task identifier.
            name (str): name of the object.
            notify_chat_id (str): notify chat id string. Defaults to ``''``.
            notify_platform (str): notify platform string. Defaults to ``''``.
        """
        self._tasks[task_id] = BackgroundTask(
            task_id=task_id,
            name=name,
            status="running",
            start_time=time.time(),
            notify_chat_id=notify_chat_id,
            notify_platform=notify_platform,
        )

    def complete_task(self, task_id: str, result: Any = None) -> None:
        """
        Complete task.

        Args:
            task_id (str): task identifier.
            result (Any): result. Defaults to ``None``.
        """
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = "completed"
            task.result = result
            task.end_time = time.time()
            self._send_notification(task, f"Task '{task.name}' completed")

    def fail_task(self, task_id: str, error: str) -> None:
        """
        Fail task.

        Args:
            task_id (str): task identifier.
            error (str): error string.
        """
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = "failed"
            task.error = error
            task.end_time = time.time()
            self._send_notification(task, f"Task '{task.name}' failed: {error}")

    def _send_notification(self, task: BackgroundTask, message: str) -> None:
        if not self._notify_fn or not task.notify_chat_id:
            return

        try:
            if asyncio.iscoroutinefunction(self._notify_fn):
                asyncio.create_task(
                    self._notify_fn(task.notify_platform, task.notify_chat_id, message)
                )
            else:
                self._notify_fn(task.notify_platform, task.notify_chat_id, message)
        except Exception as e:
            logger.warning(f"Failed to send notification: {e}")

    def get_active_tasks(self) -> list[dict]:
        """
        Return the active tasks.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        return [
            {
                "id": t.task_id,
                "name": t.name,
                "status": t.status,
                "start_time": t.start_time,
            }
            for t in self._tasks.values()
            if t.status in ("pending", "running")
        ]

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
                "id": task.task_id,
                "name": task.name,
                "status": task.status,
                "result": task.result,
                "error": task.error,
            }
        return None

    def cleanup_old(self, max_age_seconds: int = 3600) -> int:
        """
        Cleanup old.

        Args:
            max_age_seconds (int): numeric value for max age seconds. Defaults to ``3600``.

        Returns:
            int: the computed numeric value.
        """
        now = time.time()
        to_remove = [
            tid
            for tid, task in self._tasks.items()
            if task.status in ("completed", "failed") and (now - task.end_time) > max_age_seconds
        ]
        for tid in to_remove:
            del self._tasks[tid]
        return len(to_remove)
