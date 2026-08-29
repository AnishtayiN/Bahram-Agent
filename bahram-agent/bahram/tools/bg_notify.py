"""Background process notifications for Bahram Agent."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


class BackgroundNotificationMode(str, Enum):
    """Background notification modes."""

    CONCISE = "concise"
    ALL = "all"
    RESULT = "result"
    ERROR = "error"
    OFF = "off"


class BackgroundProcessNotifier:
    """Notify about background process status."""

    def __init__(self, mode: BackgroundNotificationMode = BackgroundNotificationMode.CONCISE) -> None:
        self.mode = mode
        self._notify_fn: Optional[Callable] = None

    def set_notify_function(self, fn: Callable) -> None:
        """Set the notification function."""
        self._notify_fn = fn

    async def notify_started(self, session_id: str, command: str) -> None:
        """Notify background process started."""
        if self.mode == BackgroundNotificationMode.OFF:
            return

        await self._send(f"🔄 Background process started: `{command[:50]}` (ID: {session_id})")

    async def notify_output(self, session_id: str, output: str) -> None:
        """Notify background process output."""
        if self.mode != BackgroundNotificationMode.ALL:
            return

        await self._send(f"📤 [{session_id}] {output[:200]}")

    async def notify_completed(self, session_id: str, exit_code: int, output: str = "") -> None:
        """Notify background process completed."""
        if self.mode == BackgroundNotificationMode.OFF:
            return

        if exit_code == 0:
            if self.mode in [BackgroundNotificationMode.CONCISE, BackgroundNotificationMode.RESULT, BackgroundNotificationMode.ALL]:
                await self._send(f"✅ Background process {session_id} completed")
        else:
            if self.mode in [BackgroundNotificationMode.CONCISE, BackgroundNotificationMode.ERROR, BackgroundNotificationMode.ALL]:
                tail = output[-200:] if output else ""
                await self._send(f"❌ Background process {session_id} failed (exit {exit_code})\n```\n{tail}\n```")

    async def notify_error(self, session_id: str, error: str) -> None:
        """Notify background process error."""
        if self.mode == BackgroundNotificationMode.OFF:
            return

        await self._send(f"❌ Background process {session_id} error: {error[:200]}")

    async def _send(self, message: str) -> None:
        """Send notification."""
        if self._notify_fn:
            try:
                await self._notify_fn(message)
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
