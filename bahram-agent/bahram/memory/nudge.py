from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

class MemoryNudge:

    def __init__(self, memory_dir: str = "data/memory") -> None:
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
        self._nudges[key] = {
            "message": message,
            "interval": interval_minutes,
            "last_nudge": datetime.now().isoformat(),
            "created": datetime.now().isoformat(),
        }
        self._save_nudges()
        logger.info(f"Set nudge: {key}")

    def remove_nudge(self, key: str) -> None:
        self._nudges.pop(key, None)
        self._save_nudges()

    def get_pending_nudges(self) -> list[dict[str, Any]]:
        now = datetime.now()
        pending = []

        for key, nudge in self._nudges.items():
            last = datetime.fromisoformat(nudge["last_nudge"])
            interval = timedelta(minutes=nudge["interval"])

            if now - last >= interval:
                pending.append({"key": key, **nudge})

        return pending

    def mark_nudged(self, key: str) -> None:
        if key in self._nudges:
            self._nudges[key]["last_nudge"] = datetime.now().isoformat()
            self._save_nudges()

    def list_nudges(self) -> dict[str, dict]:
        return self._nudges.copy()

    def save_lesson(self, lesson: str, context: str = "") -> str:
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
        lessons = []
        query_lower = query.lower()

        for lesson_file in self.memory_dir.glob("lesson_*.json"):
            try:
                with open(lesson_file) as f:
                    data = json.load(f)
                    if query_lower in data.get("lesson", "").lower():
                        lessons.append(data)
            except Exception:
                continue

        return lessons

    def get_recent_lessons(self, limit: int = 10) -> list[dict]:
        lessons = []
        for lesson_file in self.memory_dir.glob("lesson_*.json"):
            try:
                with open(lesson_file) as f:
                    lessons.append(json.load(f))
            except Exception:
                continue

        lessons.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return lessons[:limit]
