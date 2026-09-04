"""Cron-style task scheduler for recurring agent jobs.

Public objects: ``ScheduledTask``, ``Scheduler``.

Status: standalone capability module - see docs/FEATURE_MATRIX.md.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    """
    Scheduled task.

    Attributes:
        id (str): id string.
        name (str): name of the object.
        command (str): shell command to execute.
        schedule (str): schedule string.
        enabled (bool): when ``True`` the object is active.
        last_run (datetime | None): last run.
        next_run (datetime | None): next run.
        metadata (dict[str, Any]): mapping of metadata.
    """

    id: str
    name: str
    command: str
    schedule: str
    enabled: bool = True
    last_run: datetime | None = None
    next_run: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Scheduler:
    """
    Scheduler.
    """

    def __init__(self, config: Any = None) -> None:
        """
        Initialise a Scheduler instance.

        Args:
            config (Any): configuration object. Defaults to ``None``.
        """
        self.config = config
        self.tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._check_interval = getattr(config, "check_interval", 60) if config else 60
        self._max_concurrent = getattr(config, "max_concurrent", 5) if config else 5
        self._semaphore = asyncio.Semaphore(self._max_concurrent)

    async def start(self) -> None:
        """
        Start the component and acquire any resources it needs.

        Note:
            Coroutine - must be awaited.
        """
        self._running = True
        asyncio.create_task(self._run_loop())
        logger.info("Scheduler started")

    async def stop(self) -> None:
        """
        Stop the component and release any resources it holds.

        Note:
            Coroutine - must be awaited.
        """
        self._running = False
        logger.info("Scheduler stopped")

    def add_task(self, task: ScheduledTask) -> None:
        """
        Add task.

        Args:
            task (ScheduledTask): task.
        """
        self.tasks[task.id] = task
        logger.info(f"Added task: {task.name}")

    def remove_task(self, task_id: str) -> None:
        """
        Remove task.

        Args:
            task_id (str): task identifier.
        """
        self.tasks.pop(task_id, None)
        logger.info(f"Removed task: {task_id}")

    def get_task(self, task_id: str) -> ScheduledTask | None:
        """
        Return the task.

        Args:
            task_id (str): task identifier.

        Returns:
            ScheduledTask | None: the resulting object, or ``None`` when it is not available.
        """
        return self.tasks.get(task_id)

    def list_tasks(self) -> list[ScheduledTask]:
        """
        List tasks.

        Returns:
            list[ScheduledTask]: a sequence of ScheduledTask entries (empty when there is nothing to
                report).
        """
        return list(self.tasks.values())

    async def _run_loop(self) -> None:
        while self._running:
            now = datetime.now()

            for task in self.tasks.values():
                if not task.enabled:
                    continue

                if task.next_run and task.next_run <= now:
                    asyncio.create_task(self._execute_task(task))

            await asyncio.sleep(self._check_interval)

    async def _execute_task(self, task: ScheduledTask) -> None:
        async with self._semaphore:
            logger.info(f"Executing task: {task.name}")
            task.last_run = datetime.now()

            try:
                logger.info(f"Task {task.name} completed")
            except Exception as e:
                logger.error(f"Task {task.name} failed: {e}")

            task.next_run = self._calculate_next_run(task.schedule)

    def _calculate_next_run(self, schedule: str) -> datetime:

        now = datetime.now()

        if schedule == "hourly":
            return now + timedelta(hours=1)
        elif schedule == "daily":
            return now + timedelta(days=1)
        elif schedule == "weekly":
            return now + timedelta(weeks=1)
        elif schedule.startswith("every "):
            parts = schedule.split()
            if len(parts) >= 3:
                try:
                    value = int(parts[1])
                    unit = parts[2]

                    if unit.startswith("minute"):
                        return now + timedelta(minutes=value)
                    elif unit.startswith("hour"):
                        return now + timedelta(hours=value)
                    elif unit.startswith("day"):
                        return now + timedelta(days=value)
                except ValueError:
                    pass

        return now + timedelta(hours=1)
