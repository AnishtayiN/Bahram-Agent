"""Session resume across gateway restarts for Bahram Agent."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ResumableSession:
    """A session that can be resumed after restart."""

    session_id: str
    platform: str
    chat_id: str
    last_turn: int = 0
    status: str = "active"  # active, restart_interrupted, resumed
    interrupted_at: Optional[str] = None
    context: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


class SessionResumeManager:
    """Manage session resume across restarts."""

    def __init__(self, data_dir: str = "data/sessions") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, ResumableSession] = {}
        self._load_sessions()

    def _load_sessions(self) -> None:
        """Load sessions from disk."""
        sessions_file = self.data_dir / "resumable.json"
        if sessions_file.exists():
            try:
                with open(sessions_file) as f:
                    data = json.load(f)
                for item in data:
                    session = ResumableSession(**item)
                    self._sessions[session.session_id] = session
            except Exception as e:
                logger.warning(f"Failed to load sessions: {e}")

    def _save_sessions(self) -> None:
        """Save sessions to disk."""
        sessions_file = self.data_dir / "resumable.json"
        data = [
            {
                "session_id": s.session_id,
                "platform": s.platform,
                "chat_id": s.chat_id,
                "last_turn": s.last_turn,
                "status": s.status,
                "interrupted_at": s.interrupted_at,
                "context": s.context,
                "metadata": s.metadata,
            }
            for s in self._sessions.values()
        ]
        with open(sessions_file, "w") as f:
            json.dump(data, f, indent=2)

    def mark_interrupted(self, session_id: str) -> None:
        """Mark session as interrupted during shutdown."""
        session = self._sessions.get(session_id)
        if session:
            session.status = "restart_interrupted"
            session.interrupted_at = datetime.now().isoformat()
            self._save_sessions()

    def mark_resumed(self, session_id: str) -> None:
        """Mark session as successfully resumed."""
        session = self._sessions.get(session_id)
        if session:
            session.status = "resumed"
            session.interrupted_at = None
            self._save_sessions()

    def get_interrupted(self) -> list[ResumableSession]:
        """Get sessions that need resuming."""
        return [
            s for s in self._sessions.values()
            if s.status == "restart_interrupted"
        ]

    def get_session(self, session_id: str) -> Optional[ResumableSession]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def update_turn(self, session_id: str, turn: int) -> None:
        """Update last turn number."""
        session = self._sessions.get(session_id)
        if session:
            session.last_turn = turn
            self._save_sessions()

    def cleanup_old(self, max_age_days: int = 7) -> int:
        """Clean up old sessions."""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=max_age_days)
        to_delete = []

        for session_id, session in self._sessions.items():
            if session.interrupted_at:
                interrupted = datetime.fromisoformat(session.interrupted_at)
                if interrupted < cutoff:
                    to_delete.append(session_id)

        for session_id in to_delete:
            del self._sessions[session_id]

        if to_delete:
            self._save_sessions()
        return len(to_delete)
