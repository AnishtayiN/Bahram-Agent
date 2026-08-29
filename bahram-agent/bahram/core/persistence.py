from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from bahram.core.engine import Message, MessageRole

logger = logging.getLogger(__name__)

class SessionStore:
    def __init__(self, db_path: str = "data/sessions.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
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
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
        """)
        conn.commit()

    def create_session(self, session_id: str, user_id: str = "", channel: str = "", model: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        conn = self._get_conn()
        now = time.time()
        conn.execute(
            "INSERT INTO sessions (id, user_id, channel, model, created_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
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
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()

    def add_message(self, session_id: str, message: Message) -> str:
        conn = self._get_conn()
        msg_id = str(uuid.uuid4())[:12]
        conn.execute(
            "INSERT INTO messages (id, session_id, role, content, name, tool_call_id, timestamp, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (msg_id, session_id, message.role.value, message.content, message.name, message.tool_call_id, message.timestamp, json.dumps(message.metadata)),
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
            messages.append(Message(
                role=MessageRole(row["role"]),
                content=row["content"],
                name=row["name"],
                tool_call_id=row["tool_call_id"],
                timestamp=row["timestamp"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            ))
        return messages

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def clear_messages(self, session_id: str) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.commit()
