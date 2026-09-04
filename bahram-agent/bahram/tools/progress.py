from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class ToolProgress:

    tool_name: str
    status: str = "pending"
    progress: float = 0.0
    message: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    result: Any = None
    error: str = ""

class ProgressTracker:

    def __init__(self) -> None:
        self._active: dict[str, ToolProgress] = {}
        self._history: list[ToolProgress] = []
        self._callbacks: list[Callable] = []

    def start(self, tool_name: str) -> str:
        import uuid
        tracker_id = f"{tool_name}_{uuid.uuid4().hex[:8]}"

        progress = ToolProgress(
            tool_name=tool_name,
            status="running",
            start_time=time.time(),
        )
        self._active[tracker_id] = progress
        self._notify_callbacks(progress)
        return tracker_id

    def update(self, tracker_id: str, progress: float = None, message: str = None) -> None:
        if tracker_id in self._active:
            p = self._active[tracker_id]
            if progress is not None:
                p.progress = progress
            if message is not None:
                p.message = message
            self._notify_callbacks(p)

    def complete(self, tracker_id: str, result: Any = None) -> None:
        if tracker_id in self._active:
            p = self._active[tracker_id]
            p.status = "completed"
            p.progress = 100
            p.end_time = time.time()
            p.result = result
            self._history.append(p)
            del self._active[tracker_id]
            self._notify_callbacks(p)

    def fail(self, tracker_id: str, error: str) -> None:
        if tracker_id in self._active:
            p = self._active[tracker_id]
            p.status = "failed"
            p.end_time = time.time()
            p.error = error
            self._history.append(p)
            del self._active[tracker_id]
            self._notify_callbacks(p)

    def get_active(self) -> list[dict]:
        return [
            {
                "id": k,
                "tool": v.tool_name,
                "status": v.status,
                "progress": v.progress,
                "message": v.message,
            }
            for k, v in self._active.items()
        ]

    def get_history(self, limit: int = 10) -> list[dict]:
        return [
            {
                "tool": p.tool_name,
                "status": p.status,
                "duration": p.end_time - p.start_time,
                "error": p.error,
            }
            for p in self._history[-limit:]
        ]

    def add_callback(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    def _notify_callbacks(self, progress: ToolProgress) -> None:
        for callback in self._callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
