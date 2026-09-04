"""
Session resume.

Public objects: ``SessionState``, ``SessionResumeManager``.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SessionState:
    """
    Session state.

    Attributes:
        session_id (str): session identifier.
        platform (str): platform string.
        chat_id (str): chat id string.
        last_message (str): last message string.
        timestamp (float): numeric value for timestamp.
        context (dict): mapping of context.
        conversation_history (list[dict]): collection of conversation history.
    """

    session_id: str
    platform: str
    chat_id: str
    last_message: str
    timestamp: float
    context: dict = field(default_factory=dict)
    conversation_history: list[dict] = field(default_factory=list)


class SessionResumeManager:
    """
    Session resume manager.
    """

    def __init__(self, data_dir: str = "data/gateway") -> None:
        """
        Initialise a SessionResumeManager instance.

        Args:
            data_dir (str): directory that holds the on-disk state. Defaults to ``'data/gateway'``.
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, SessionState] = {}
        self._load()

    def _load(self) -> None:
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
        sessions_file = self.data_dir / "sessions.json"
        data = [
            {
                "session_id": s.session_id,
                "platform": s.platform,
                "chat_id": s.chat_id,
                "last_message": s.last_message,
                "timestamp": s.timestamp,
                "context": s.context,
                "conversation_history": s.conversation_history[-10:],
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
        """
        Save session.

        Args:
            session_id (str): session identifier.
            platform (str): platform string.
            chat_id (str): chat id string.
            last_message (str): last message string.
            context (dict): mapping of context. Defaults to ``None``.
            history (list[dict]): collection of history. Defaults to ``None``.
        """
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

    def get_session(self, session_id: str) -> SessionState | None:
        """
        Return the session.

        Args:
            session_id (str): session identifier.

        Returns:
            SessionState | None: the resulting object, or ``None`` when it is not available.
        """
        return self._sessions.get(session_id)

    def get_recent_sessions(self, platform: str = None, limit: int = 10) -> list[dict]:
        """
        Return the recent sessions.

        Args:
            platform (str): platform string. Defaults to ``None``.
            limit (int): maximum number of items to return. Defaults to ``10``.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
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
        """
        Cleanup old.

        Args:
            max_age_seconds (int): numeric value for max age seconds. Defaults to ``86400``.

        Returns:
            int: the computed numeric value.
        """
        now = time.time()
        to_remove = [
            sid
            for sid, session in self._sessions.items()
            if (now - session.timestamp) > max_age_seconds
        ]
        for sid in to_remove:
            del self._sessions[sid]
        if to_remove:
            self._save()
        return len(to_remove)
