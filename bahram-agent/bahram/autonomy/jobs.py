from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    PAUSED = "paused"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


PRIORITY_ORDER = {
    JobPriority.CRITICAL: 0,
    JobPriority.HIGH: 1,
    JobPriority.NORMAL: 2,
    JobPriority.LOW: 3,
}


@dataclass
class Job:
    id: str
    run_id: str
    session_id: str
    parent_job_id: str | None = None
    state: JobStatus = JobStatus.QUEUED
    priority: JobPriority = JobPriority.NORMAL
    payload: dict[str, Any] = field(default_factory=dict)
    checkpoint_id: str | None = None
    attempt_count: int = 0
    max_attempts: int = 3
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    updated_at: float | None = None
    finished_at: float | None = None
    result: str | None = None
    error: str | None = None
    user_id: str = ""
    capabilities: list[str] = field(default_factory=list)
    security_policy: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "session_id": self.session_id,
            "parent_job_id": self.parent_job_id,
            "state": self.state.value,
            "priority": self.priority.value,
            "payload": self.payload,
            "checkpoint_id": self.checkpoint_id,
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error,
            "user_id": self.user_id,
            "capabilities": self.capabilities,
            "security_policy": self.security_policy,
        }


JobHandler = Callable[..., Coroutine[Any, Any, str]]


class JobEngine:
    def __init__(self, data_dir: str = "data/jobs", max_concurrent: int = 3) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._data_dir / "jobs.db"
        self._local = threading.local()
        self._handlers: dict[str, JobHandler] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._max_concurrent = max_concurrent
        self._active_count = 0
        self._init_db()
        self._load_pending_jobs()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._db_path))
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                run_id TEXT,
                session_id TEXT,
                parent_job_id TEXT,
                state TEXT,
                priority TEXT,
                payload TEXT,
                checkpoint_id TEXT,
                attempt_count INTEGER DEFAULT 0,
                max_attempts INTEGER DEFAULT 3,
                created_at REAL,
                started_at REAL,
                updated_at REAL,
                finished_at REAL,
                result TEXT,
                error TEXT,
                user_id TEXT,
                capabilities TEXT,
                security_policy TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);
            CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority);
            CREATE INDEX IF NOT EXISTS idx_jobs_session ON jobs(session_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_parent ON jobs(parent_job_id);
        """)
        conn.commit()

    def _load_pending_jobs(self) -> None:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM jobs WHERE state IN (?, ?, ?)",
            (JobStatus.RUNNING.value, JobStatus.STARTING.value, JobStatus.RETRYING.value),
        ).fetchall()
        for row in rows:
            job = self._row_to_job(row)
            logger.info(f"Found pending job on startup: {job.id} (state={job.state.value})")

    def _row_to_job(self, row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            run_id=row["run_id"],
            session_id=row["session_id"],
            parent_job_id=row["parent_job_id"],
            state=JobStatus(row["state"]),
            priority=JobPriority(row["priority"]),
            payload=json.loads(row["payload"]) if row["payload"] else {},
            checkpoint_id=row["checkpoint_id"],
            attempt_count=row["attempt_count"],
            max_attempts=row["max_attempts"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            updated_at=row["updated_at"],
            finished_at=row["finished_at"],
            result=row["result"],
            error=row["error"],
            user_id=row["user_id"] or "",
            capabilities=json.loads(row["capabilities"]) if row["capabilities"] else [],
            security_policy=json.loads(row["security_policy"]) if row["security_policy"] else {},
        )

    def _save_job(self, job: Job) -> None:
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO jobs
            (id, run_id, session_id, parent_job_id, state, priority, payload,
             checkpoint_id, attempt_count, max_attempts, created_at, started_at,
             updated_at, finished_at, result, error, user_id, capabilities, security_policy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job.id, job.run_id, job.session_id, job.parent_job_id,
                job.state.value, job.priority.value, json.dumps(job.payload),
                job.checkpoint_id, job.attempt_count, job.max_attempts,
                job.created_at, job.started_at, job.updated_at, job.finished_at,
                job.result, job.error, job.user_id,
                json.dumps(job.capabilities), json.dumps(job.security_policy),
            ),
        )
        conn.commit()

    def register_handler(self, job_type: str, handler: JobHandler) -> None:
        self._handlers[job_type] = handler

    async def enqueue(
        self,
        job_type: str,
        run_id: str,
        session_id: str,
        payload: dict[str, Any] | None = None,
        priority: JobPriority = JobPriority.NORMAL,
        parent_job_id: str | None = None,
        user_id: str = "",
        capabilities: list[str] | None = None,
        security_policy: dict[str, Any] | None = None,
    ) -> Job:
        job = Job(
            id=f"job_{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            session_id=session_id,
            parent_job_id=parent_job_id,
            state=JobStatus.QUEUED,
            priority=priority,
            payload=payload or {},
            user_id=user_id,
            capabilities=capabilities or [],
            security_policy=security_policy or {},
        )
        self._save_job(job)
        logger.info(f"Enqueued job {job.id} (type={job_type}, priority={priority.value})")
        return job

    async def start_job(self, job: Job) -> None:
        if self._active_count >= self._max_concurrent:
            logger.warning(f"Cannot start job {job.id}: max concurrent jobs reached")
            return

        job.state = JobStatus.STARTING
        job.started_at = time.time()
        job.attempt_count += 1
        self._save_job(job)

        handler = self._handlers.get(job.payload.get("type", ""))
        if not handler:
            job.state = JobStatus.FAILED
            job.error = f"No handler for job type: {job.payload.get('type', '')}"
            job.finished_at = time.time()
            self._save_job(job)
            return

        self._active_count += 1
        task = asyncio.create_task(self._run_job(job, handler))
        self._running_tasks[job.id] = task

    async def _run_job(self, job: Job, handler: JobHandler) -> None:
        try:
            job.state = JobStatus.RUNNING
            self._save_job(job)

            result = await handler(
                job_id=job.id,
                run_id=job.run_id,
                session_id=job.session_id,
                **job.payload,
            )

            job.state = JobStatus.COMPLETED
            job.result = result
            job.finished_at = time.time()
            self._save_job(job)
            logger.info(f"Job {job.id} completed successfully")

        except Exception as e:
            logger.error(f"Job {job.id} failed: {e}")
            job.error = str(e)

            if job.attempt_count < job.max_attempts:
                job.state = JobStatus.RETRYING
                self._save_job(job)
                await asyncio.sleep(min(30, 2 ** job.attempt_count))
                await self.start_job(job)
            else:
                job.state = JobStatus.FAILED
                job.finished_at = time.time()
                self._save_job(job)
        finally:
            self._active_count -= 1
            self._running_tasks.pop(job.id, None)

    async def cancel_job(self, job_id: str) -> bool:
        task = self._running_tasks.get(job_id)
        if task:
            task.cancel()
            conn = self._get_conn()
            conn.execute(
                "UPDATE jobs SET state = ?, updated_at = ?, finished_at = ? WHERE id = ?",
                (JobStatus.CANCELLED.value, time.time(), time.time(), job_id),
            )
            conn.commit()
            return True
        return False

    def get_job(self, job_id: str) -> Job | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row:
            return self._row_to_job(row)
        return None

    def list_jobs(
        self,
        session_id: str | None = None,
        state: JobStatus | None = None,
        limit: int = 50,
    ) -> list[Job]:
        conn = self._get_conn()
        query = "SELECT * FROM jobs WHERE 1=1"
        params: list[Any] = []
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if state:
            query += " AND state = ?"
            params.append(state.value)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [self._row_to_job(r) for r in rows]

    def get_queue_depth(self) -> dict[str, int]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT state, COUNT(*) as cnt FROM jobs GROUP BY state"
        ).fetchall()
        return {row["state"]: row["cnt"] for row in rows}
