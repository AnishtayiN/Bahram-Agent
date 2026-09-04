"""
Progress.

Public objects: ``ToolProgress``, ``ProgressTracker``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolProgress:
    """
    Tool progress.

    Attributes:
        tool_name (str): tool name string.
        status (str): status string.
        progress (float): numeric value for progress.
        message (str): message to process.
        start_time (float): numeric value for start time.
        end_time (float): numeric value for end time.
        result (Any): result.
        error (str): error string.
    """

    tool_name: str
    status: str = "pending"
    progress: float = 0.0
    message: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    result: Any = None
    error: str = ""


class ProgressTracker:
    """
    Progress tracker.
    """

    def __init__(self) -> None:
        """
        Initialise a ProgressTracker instance.
        """
        self._active: dict[str, ToolProgress] = {}
        self._history: list[ToolProgress] = []
        self._callbacks: list[Callable] = []

    def start(self, tool_name: str) -> str:
        """
        Start the component and acquire any resources it needs.

        Args:
            tool_name (str): tool name string.

        Returns:
            str: the rendered string.
        """
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
        """
        Update.

        Args:
            tracker_id (str): tracker id string.
            progress (float): numeric value for progress. Defaults to ``None``.
            message (str): message to process. Defaults to ``None``.
        """
        if tracker_id in self._active:
            p = self._active[tracker_id]
            if progress is not None:
                p.progress = progress
            if message is not None:
                p.message = message
            self._notify_callbacks(p)

    def complete(self, tracker_id: str, result: Any = None) -> None:
        """
        Complete.

        Args:
            tracker_id (str): tracker id string.
            result (Any): result. Defaults to ``None``.
        """
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
        """
        Fail.

        Args:
            tracker_id (str): tracker id string.
            error (str): error string.
        """
        if tracker_id in self._active:
            p = self._active[tracker_id]
            p.status = "failed"
            p.end_time = time.time()
            p.error = error
            self._history.append(p)
            del self._active[tracker_id]
            self._notify_callbacks(p)

    def get_active(self) -> list[dict]:
        """
        Return the active.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
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
        """
        Return the history.

        Args:
            limit (int): maximum number of items to return. Defaults to ``10``.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
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
        """
        Add callback.

        Args:
            callback (Callable): callable used for callback.
        """
        self._callbacks.append(callback)

    def _notify_callbacks(self, progress: ToolProgress) -> None:
        for callback in self._callbacks:
            try:
                callback(progress)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
