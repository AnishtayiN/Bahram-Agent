"""
Nudge.

Public objects: ``MemoryNudge``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MemoryNudge:
    """
    Memory nudge.
    """

    def __init__(self, memory_dir: str = "data/memory") -> None:
        """
        Initialise a MemoryNudge instance.

        Args:
            memory_dir (str): memory dir string. Defaults to ``'data/memory'``.
        """
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._nudges: dict[str, dict] = {}
        self._load_nudges()

    def _load_nudges(self) -> None:
        nudge_file = self.memory_dir / "nudges.json"
        if nudge_file.exists():
            try:
                with open(nudge_file) as f:
                    self._nudges = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load nudges: {e}")

    def _save_nudges(self) -> None:
        nudge_file = self.memory_dir / "nudges.json"
        try:
            with open(nudge_file, "w") as f:
                json.dump(self._nudges, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save nudges: {e}")

    def set_nudge(self, key: str, message: str, interval_minutes: int = 60) -> None:
        """
        Set the nudge.

        Args:
            key (str): key string.
            message (str): message to process.
            interval_minutes (int): numeric value for interval minutes. Defaults to ``60``.
        """
        self._nudges[key] = {
            "message": message,
            "interval": interval_minutes,
            "last_nudge": datetime.now().isoformat(),
            "created": datetime.now().isoformat(),
        }
        self._save_nudges()
        logger.info(f"Set nudge: {key}")

    def remove_nudge(self, key: str) -> None:
        """
        Remove nudge.

        Args:
            key (str): key string.
        """
        self._nudges.pop(key, None)
        self._save_nudges()

    def get_pending_nudges(self) -> list[dict[str, Any]]:
        """
        Return the pending nudges.

        Returns:
            list[dict[str, Any]]: a sequence of dict[str, Any] entries (empty when there is nothing
                to report).
        """
        now = datetime.now()
        pending = []

        for key, nudge in self._nudges.items():
            last = datetime.fromisoformat(nudge["last_nudge"])
            interval = timedelta(minutes=nudge["interval"])

            if now - last >= interval:
                pending.append({"key": key, **nudge})

        return pending

    def mark_nudged(self, key: str) -> None:
        """
        Mark nudged.

        Args:
            key (str): key string.
        """
        if key in self._nudges:
            self._nudges[key]["last_nudge"] = datetime.now().isoformat()
            self._save_nudges()

    def list_nudges(self) -> dict[str, dict]:
        """
        List nudges.

        Returns:
            dict[str, dict]: a mapping of str, dict.
        """
        return self._nudges.copy()

    def save_lesson(self, lesson: str, context: str = "") -> str:
        """
        Save lesson.

        Args:
            lesson (str): lesson string.
            context (str): context string. Defaults to ``''``.

        Returns:
            str: the rendered string.
        """
        import uuid

        lesson_id = str(uuid.uuid4())[:8]
        lesson_file = self.memory_dir / f"lesson_{lesson_id}.json"

        data = {
            "id": lesson_id,
            "lesson": lesson,
            "context": context,
            "timestamp": datetime.now().isoformat(),
            "accessed": 0,
        }

        try:
            with open(lesson_file, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved lesson: {lesson_id}")
            return lesson_id
        except Exception as e:
            logger.error(f"Failed to save lesson: {e}")
            return ""

    def search_lessons(self, query: str) -> list[dict]:
        """
        Search lessons.

        Args:
            query (str): search query.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        lessons = []
        query_lower = query.lower()

        for lesson_file in self.memory_dir.glob("lesson_*.json"):
            try:
                with open(lesson_file) as f:
                    data = json.load(f)
                    if query_lower in data.get("lesson", "").lower():
                        lessons.append(data)
            except Exception as e:
                logger.warning("Skipping unreadable lesson file: %s", e)
                continue

        return lessons

    def get_recent_lessons(self, limit: int = 10) -> list[dict]:
        """
        Return the recent lessons.

        Args:
            limit (int): maximum number of items to return. Defaults to ``10``.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        lessons = []
        for lesson_file in self.memory_dir.glob("lesson_*.json"):
            try:
                with open(lesson_file) as f:
                    lessons.append(json.load(f))
            except Exception:
                logger.error(
                    "Swallowed exception in nudge",
                    exc_info=True,
                )
                continue

        lessons.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return lessons[:limit]
