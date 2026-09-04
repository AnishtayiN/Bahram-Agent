from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from bahram.core.engine import Message, MessageRole, Trajectory

logger = logging.getLogger(__name__)


class SessionStore:
    def __init__(self, db_path: str = "data/sessions.db") -> None:
        self._memory_only = str(db_path) == ":memory:"
        self._db_path = Path(db_path) if not self._memory_only else None
        self._memory_conn: sqlite3.Connection | None = None
        if self._db_path is not None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._memory_only:
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(":memory:")
                self._memory_conn.row_factory = sqlite3.Row
            return self._memory_conn
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._db_path))
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                channel TEXT,
                model TEXT,
                created_at REAL,
                updated_at REAL,
                metadata TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                role TEXT,
                content TEXT,
                name TEXT,
                tool_call_id TEXT,
                timestamp REAL,
                metadata TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                goal TEXT,
                model TEXT,
                provider TEXT,
                status TEXT,
                final_content TEXT,
                total_tool_calls INTEGER DEFAULT 0,
                total_duration_ms REAL DEFAULT 0,
                started_at REAL,
                finished_at REAL,
                metadata TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
            CREATE TABLE IF NOT EXISTS trajectory_steps (
                id TEXT PRIMARY KEY,
                run_id TEXT,
                step_id TEXT,
                iteration INTEGER,
                provider TEXT,
                model TEXT,
                tool_calls TEXT,
                tool_results TEXT,
                content_length INTEGER,
                duration_ms REAL,
                state TEXT,
                error TEXT,
                timestamp REAL,
                FOREIGN KEY (run_id) REFERENCES runs(id)
            );
            CREATE TABLE IF NOT EXISTS tool_calls (
                id TEXT PRIMARY KEY,
                run_id TEXT,
                tool_name TEXT,
                arguments TEXT,
                status TEXT,
                result TEXT,
                error TEXT,
                duration_ms REAL,
                timestamp REAL,
                FOREIGN KEY (run_id) REFERENCES runs(id)
            );
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                event_type TEXT,
                source TEXT,
                data TEXT,
                timestamp REAL
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
            CREATE INDEX IF NOT EXISTS idx_runs_session ON runs(session_id);
            CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
            CREATE INDEX IF NOT EXISTS idx_tool_calls_run ON tool_calls(run_id);
            CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
            CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
        """)
        conn.commit()

    def create_session(
        self,
        session_id: str,
        user_id: str = "",
        channel: str = "",
        model: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        conn = self._get_conn()
        now = time.time()
        conn.execute(
            (
                "INSERT INTO sessions (id, user_id, channel, model, created_at, updated_at, "
                "metadata) VALUES (?, ?, ?, ?, ?, ?, ?)"
            ),
            (session_id, user_id, channel, model, now, now, json.dumps(metadata or {})),
        )
        conn.commit()
        return {"id": session_id, "created_at": now, "updated_at": now}

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row:
            return dict(row)
        return None

    def update_session(self, session_id: str, **kwargs: Any) -> None:
        conn = self._get_conn()
        sets = ["updated_at = ?"]
        values: list[Any] = [time.time()]
        for key in ("user_id", "channel", "model"):
            if key in kwargs:
                sets.append(f"{key} = ?")
                values.append(kwargs[key])
        if "metadata" in kwargs:
            sets.append("metadata = ?")
            values.append(json.dumps(kwargs["metadata"]))
        values.append(session_id)
        conn.execute(f"UPDATE sessions SET {', '.join(sets)} WHERE id = ?", values)
        conn.commit()

    def delete_session(self, session_id: str) -> None:
        conn = self._get_conn()
        run_ids = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM runs WHERE session_id = ?", (session_id,)
            ).fetchall()
        ]
        for rid in run_ids:
            conn.execute("DELETE FROM trajectory_steps WHERE run_id = ?", (rid,))
            conn.execute("DELETE FROM tool_calls WHERE run_id = ?", (rid,))
        conn.execute("DELETE FROM runs WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()

    def add_message(self, session_id: str, message: Message) -> str:
        conn = self._get_conn()
        msg_id = str(uuid.uuid4())[:12]
        conn.execute(
            (
                "INSERT INTO messages (id, session_id, role, content, name, tool_call_id, "
                "timestamp, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                msg_id,
                session_id,
                message.role.value,
                message.content,
                message.name,
                message.tool_call_id,
                message.timestamp,
                json.dumps(message.metadata),
            ),
        )
        conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (time.time(), session_id))
        conn.commit()
        return msg_id

    def get_messages(self, session_id: str, limit: int = 100) -> list[Message]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        messages = []
        for row in reversed(rows):
            messages.append(
                Message(
                    role=MessageRole(row["role"]),
                    content=row["content"],
                    name=row["name"],
                    tool_call_id=row["tool_call_id"],
                    timestamp=row["timestamp"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                )
            )
        return messages

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def clear_messages(self, session_id: str) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()

    def save_trajectory(self, trajectory: Trajectory, session_id: str) -> str:
        conn = self._get_conn()
        run_id = trajectory.run_id
        conn.execute(
            "INSERT INTO runs (id, session_id, goal, model, provider, status, "
            "final_content, total_tool_calls, total_duration_ms, started_at, "
            "finished_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                session_id,
                trajectory.goal,
                trajectory.model,
                trajectory.provider,
                trajectory.status,
                trajectory.final_content,
                trajectory.total_tool_calls,
                trajectory.total_duration_ms,
                trajectory.started_at,
                trajectory.finished_at,
                "{}",
            ),
        )
        for step in trajectory.steps:
            conn.execute(
                "INSERT INTO trajectory_steps (id, run_id, step_id, iteration, "
                "provider, model, tool_calls, tool_results, content_length, "
                "duration_ms, state, error, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"{run_id}_{step.step_id}",
                    run_id,
                    step.step_id,
                    step.iteration,
                    step.provider,
                    step.model,
                    json.dumps(step.tool_calls),
                    json.dumps(step.tool_results),
                    step.content_length,
                    step.duration_ms,
                    step.state,
                    step.error,
                    step.timestamp,
                ),
            )
        conn.commit()
        return run_id

    def get_trajectory(self, run_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not run:
            return None
        steps = conn.execute(
            "SELECT * FROM trajectory_steps WHERE run_id = ? ORDER BY iteration", (run_id,)
        ).fetchall()
        return {
            "run": dict(run),
            "steps": [dict(s) for s in steps],
        }

    def log_tool_call(
        self,
        run_id: str,
        tool_name: str,
        arguments: dict,
        status: str,
        result: str = "",
        error: str = "",
        duration_ms: float = 0,
    ) -> str:
        conn = self._get_conn()
        call_id = str(uuid.uuid4())[:12]
        conn.execute(
            (
                "INSERT INTO tool_calls (id, run_id, tool_name, arguments, status, result, error, "
                "duration_ms, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                call_id,
                run_id,
                tool_name,
                json.dumps(arguments),
                status,
                result[:10000],
                error,
                duration_ms,
                time.time(),
            ),
        )
        conn.commit()
        return call_id

    def log_event(self, event_type: str, source: str = "", data: dict | None = None) -> str:
        conn = self._get_conn()
        event_id = str(uuid.uuid4())[:12]
        conn.execute(
            "INSERT INTO events (id, event_type, source, data, timestamp) VALUES (?, ?, ?, ?, ?)",
            (event_id, event_type, source, json.dumps(data or {}), time.time()),
        )
        conn.commit()
        return event_id

    def get_events(self, event_type: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._get_conn()
        if event_type:
            rows = conn.execute(
                "SELECT * FROM events WHERE event_type = ? ORDER BY timestamp DESC LIMIT ?",
                (event_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
