from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class JobState(str, Enum):
    SCHEDULED = "scheduled"
    PAUSED = "paused"
    RUNNING = "running"
    COMPLETED = "completed"


@dataclass
class CronJob:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    prompt: str = ""
    schedule: str = ""
    state: JobState = JobState.SCHEDULED
    skills: list[str] = field(default_factory=list)
    script: str = ""
    context_from: list[str] = field(default_factory=list)
    continuity: bool = False
    deliver_to: str = "origin"
    repeat: int = 0
    run_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_run: str | None = None
    next_run: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CronScheduler:
    def __init__(self, data_dir: str = "data/cron") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, CronJob] = {}
        self._lock = asyncio.Lock()
        self._running = False
        self._tick_interval = 60
        self._handlers: dict[str, Callable] = {}
        self._load_jobs()

    def _load_jobs(self) -> None:
        jobs_file = self.data_dir / "jobs.json"
        if jobs_file.exists():
            try:
                with open(jobs_file) as f:
                    data = json.load(f)
                    for job_data in data:
                        job = CronJob(**job_data)
                        self.jobs[job.id] = job
            except Exception as e:
                logger.error(f"Failed to load jobs: {e}")

    def _save_jobs(self) -> None:
        jobs_file = self.data_dir / "jobs.json"
        try:
            data = [
                {
                    "id": job.id,
                    "name": job.name,
                    "prompt": job.prompt,
                    "schedule": job.schedule,
                    "state": job.state.value,
                    "skills": job.skills,
                    "script": job.script,
                    "context_from": job.context_from,
                    "continuity": job.continuity,
                    "deliver_to": job.deliver_to,
                    "repeat": job.repeat,
                    "run_count": job.run_count,
                    "created_at": job.created_at,
                    "last_run": job.last_run,
                    "next_run": job.next_run,
                    "metadata": job.metadata,
                }
                for job in self.jobs.values()
            ]
            with open(jobs_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save jobs: {e}")

    def create_job(
        self,
        prompt: str,
        schedule: str,
        name: str = "",
        skills: list[str] = None,
        deliver_to: str = "origin",
        repeat: int = 0,
    ) -> CronJob:
        job = CronJob(
            name=name or f"job-{uuid.uuid4().hex[:6]}",
            prompt=prompt,
            schedule=schedule,
            skills=skills or [],
            deliver_to=deliver_to,
            repeat=repeat,
            next_run=self._calculate_next_run(schedule),
        )
        self.jobs[job.id] = job
        self._save_jobs()
        logger.info(f"Created cron job: {job.name}")
        return job

    def get_job(self, job_id: str) -> CronJob | None:
        return self.jobs.get(job_id)

    def list_jobs(self) -> list[CronJob]:
        return list(self.jobs.values())

    def pause_job(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if job:
            job.state = JobState.PAUSED
            self._save_jobs()
            return True
        return False

    def resume_job(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if job:
            job.state = JobState.SCHEDULED
            job.next_run = self._calculate_next_run(job.schedule)
            self._save_jobs()
            return True
        return False

    def remove_job(self, job_id: str) -> bool:
        if job_id in self.jobs:
            del self.jobs[job_id]
            self._save_jobs()
            return True
        return False

    def update_job(self, job_id: str, updates: dict) -> bool:
        job = self.jobs.get(job_id)
        if job:
            for key, value in updates.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            self._save_jobs()
            return True
        return False

    def _calculate_next_run(self, schedule: str) -> str:
        now = datetime.now()

        if schedule.startswith("every "):
            parts = schedule[6:].split()
            delta = timedelta()
            for part in parts:
                if part.endswith("h"):
                    delta += timedelta(hours=int(part[:-1]))
                elif part.endswith("m"):
                    delta += timedelta(minutes=int(part[:-1]))
                elif part.endswith("s"):
                    delta += timedelta(seconds=int(part[:-1]))
            return (now + delta).isoformat()

        return (now + timedelta(hours=1)).isoformat()

    def get_due_jobs(self) -> list[CronJob]:
        now = datetime.now()
        due = []

        for job in self.jobs.values():
            if job.state != JobState.SCHEDULED:
                continue

            if job.next_run:
                next_run = datetime.fromisoformat(job.next_run)
                if next_run <= now:
                    due.append(job)

        return due

    async def start(self) -> None:
        self._running = True
        asyncio.create_task(self._tick_loop())
        logger.info("Cron scheduler started")

    async def stop(self) -> None:
        self._running = False
        logger.info("Cron scheduler stopped")

    async def _tick_loop(self) -> None:
        while self._running:
            async with self._lock:
                due_jobs = self.get_due_jobs()
                for job in due_jobs:
                    await self._run_job(job)

            await asyncio.sleep(self._tick_interval)

    async def _run_job(self, job: CronJob) -> None:
        logger.info(f"Running cron job: {job.name}")
        job.state = JobState.RUNNING
        job.last_run = datetime.now().isoformat()
        job.run_count += 1

        try:
            result = await self._execute_job(job)

            await self._deliver_result(job, result)

            if job.repeat > 0 and job.run_count >= job.repeat:
                job.state = JobState.COMPLETED
            else:
                job.state = JobState.SCHEDULED
                job.next_run = self._calculate_next_run(job.schedule)

        except Exception as e:
            logger.error(f"Job execution failed: {e}")
            job.state = JobState.SCHEDULED
            job.next_run = self._calculate_next_run(job.schedule)

        self._save_jobs()

    async def _execute_job(self, job: CronJob) -> str:

        return f"Job {job.name} executed at {datetime.now().isoformat()}"

    async def _deliver_result(self, job: CronJob, result: str) -> None:

        output_dir = self.data_dir / "output" / job.id
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(output_file, "w") as f:
            f.write(result)

        logger.info(f"Delivered result for job: {job.name}")

    def register_handler(self, event: str, handler: Callable) -> None:
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)

    async def trigger_job(self, job_id: str) -> str | None:
        job = self.jobs.get(job_id)
        if job:
            result = await self._execute_job(job)
            await self._deliver_result(job, result)
            return result
        return None
