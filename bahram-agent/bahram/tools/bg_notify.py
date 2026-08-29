"""Background task notifications for Bahram Agent."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class BackgroundTask:
    """A background task."""

    task_id: str
    name: str
    status: str = "pending"  # pending, running, completed, failed
    result: Any = None
    error: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    notify_chat_id: str = ""
    notify_platform: str = ""


class BackgroundNotifier:
    """Manage background task notifications."""

    def __init__(self) -> None:
        self._tasks: dict[str, BackgroundTask] = {}
        self._notify_fn: Optional[Callable] = None

    def set_notify_function(self, fn: Callable) -> None:
        """Set notification function."""
        self._notify_fn = fn

    def start_task(
        self,
        task_id: str,
        name: str,
        notify_chat_id: str = "",
        notify_platform: str = "",
    ) -> None:
        """Start tracking a background task."""
        self._tasks[task_id] = BackgroundTask(
            task_id=task_id,
            name=name,
            status="running",
            start_time=time.time(),
            notify_chat_id=notify_chat_id,
            notify_platform=notify_platform,
        )

    def complete_task(self, task_id: str, result: Any = None) -> None:
        """Mark task as completed."""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = "completed"
            task.result = result
            task.end_time = time.time()
            self._send_notification(task, f"Task '{task.name}' completed")

    def fail_task(self, task_id: str, error: str) -> None:
        """Mark task as failed."""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = "failed"
            task.error = error
            task.end_time = time.time()
            self._send_notification(task, f"Task '{task.name}' failed: {error}")

    def _send_notification(self, task: BackgroundTask, message: str) -> None:
        """Send notification."""
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
        """Get active tasks."""
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

    def get_task(self, task_id: str) -> Optional[dict]:
        """Get task info."""
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
        """Cleanup old completed tasks."""
        now = time.time()
        to_remove = [
            tid for tid, task in self._tasks.items()
            if task.status in ("completed", "failed")
            and (now - task.end_time) > max_age_seconds
        ]
        for tid in to_remove:
            del self._tasks[tid]
        return len(to_remove)
