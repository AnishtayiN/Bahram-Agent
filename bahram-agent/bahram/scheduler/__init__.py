"""Scheduler for Bahram Agent."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    """A scheduled task."""

    id: str
    name: str
    command: str
    schedule: str  # cron-like schedule
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class Scheduler:
    """Task scheduler for automated jobs."""

    def __init__(self, config: Any = None) -> None:
        self.config = config
        self.tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._check_interval = getattr(config, "check_interval", 60) if config else 60
        self._max_concurrent = getattr(config, "max_concurrent", 5) if config else 5
        self._semaphore = asyncio.Semaphore(self._max_concurrent)

    async def start(self) -> None:
        """Start the scheduler."""
        self._running = True
        asyncio.create_task(self._run_loop())
        logger.info("Scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        logger.info("Scheduler stopped")

    def add_task(self, task: ScheduledTask) -> None:
        """Add a scheduled task."""
        self.tasks[task.id] = task
        logger.info(f"Added task: {task.name}")

    def remove_task(self, task_id: str) -> None:
        """Remove a scheduled task."""
        self.tasks.pop(task_id, None)
        logger.info(f"Removed task: {task_id}")

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def list_tasks(self) -> list[ScheduledTask]:
        """List all tasks."""
        return list(self.tasks.values())

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            now = datetime.now()

            for task in self.tasks.values():
                if not task.enabled:
                    continue

                if task.next_run and task.next_run <= now:
                    asyncio.create_task(self._execute_task(task))

            await asyncio.sleep(self._check_interval)

    async def _execute_task(self, task: ScheduledTask) -> None:
        """Execute a scheduled task."""
        async with self._semaphore:
            logger.info(f"Executing task: {task.name}")
            task.last_run = datetime.now()

            try:
                # In a real implementation, this would execute the task
                # For now, just log it
                logger.info(f"Task {task.name} completed")
            except Exception as e:
                logger.error(f"Task {task.name} failed: {e}")

            # Calculate next run time
            task.next_run = self._calculate_next_run(task.schedule)

    def _calculate_next_run(self, schedule: str) -> datetime:
        """Calculate next run time from schedule."""
        # Simple implementation - in production, use croniter or similar
        now = datetime.now()

        # Parse simple schedules
        if schedule == "hourly":
            return now + timedelta(hours=1)
        elif schedule == "daily":
            return now + timedelta(days=1)
        elif schedule == "weekly":
            return now + timedelta(weeks=1)
        elif schedule.startswith("every "):
            # Parse "every X minutes/hours/days"
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

        # Default: run in 1 hour
        return now + timedelta(hours=1)
