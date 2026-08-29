"""Session resume after gateway restart for Bahram Agent."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """Session state for resume."""

    session_id: str
    platform: str
    chat_id: str
    last_message: str
    timestamp: float
    context: dict = field(default_factory=dict)
    conversation_history: list[dict] = field(default_factory=list)


class SessionResumeManager:
    """Manage session state for gateway restarts."""

    def __init__(self, data_dir: str = "data/gateway") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, SessionState] = {}
        self._load()

    def _load(self) -> None:
        """Load sessions from disk."""
        sessions_file = self.data_dir / "sessions.json"
        if sessions_file.exists():
            try:
                with open(sessions_file) as f:
                    data = json.load(f)
                for session_data in data:
                    session = SessionState(**session_data)
                    self._sessions[session.session_id] = session
            except Exception as e:
                logger.warning(f"Failed to load sessions: {e}")

    def _save(self) -> None:
        """Save sessions to disk."""
        sessions_file = self.data_dir / "sessions.json"
        data = [
            {
                "session_id": s.session_id,
                "platform": s.platform,
                "chat_id": s.chat_id,
                "last_message": s.last_message,
                "timestamp": s.timestamp,
                "context": s.context,
                "conversation_history": s.conversation_history[-10:],  # Keep last 10
            }
            for s in self._sessions.values()
        ]
        with open(sessions_file, "w") as f:
            json.dump(data, f, indent=2)

    def save_session(
        self,
        session_id: str,
        platform: str,
        chat_id: str,
        last_message: str,
        context: dict = None,
        history: list[dict] = None,
    ) -> None:
        """Save session state."""
        self._sessions[session_id] = SessionState(
            session_id=session_id,
            platform=platform,
            chat_id=chat_id,
            last_message=last_message,
            timestamp=time.time(),
            context=context or {},
            conversation_history=history or [],
        )
        self._save()

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Get session by ID."""
        return self._sessions.get(session_id)

    def get_recent_sessions(self, platform: str = None, limit: int = 10) -> list[dict]:
        """Get recent sessions."""
        sessions = list(self._sessions.values())
        if platform:
            sessions = [s for s in sessions if s.platform == platform]

        sessions.sort(key=lambda s: s.timestamp, reverse=True)
        return [
            {
                "session_id": s.session_id,
                "platform": s.platform,
                "chat_id": s.chat_id,
                "last_message": s.last_message[:100],
                "timestamp": s.timestamp,
            }
            for s in sessions[:limit]
        ]

    def cleanup_old(self, max_age_seconds: int = 86400) -> int:
        """Cleanup old sessions."""
        now = time.time()
        to_remove = [
            sid for sid, session in self._sessions.items()
            if (now - session.timestamp) > max_age_seconds
        ]
        for sid in to_remove:
            del self._sessions[sid]
        if to_remove:
            self._save()
        return len(to_remove)
