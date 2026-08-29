"""Busy input modes for Bahram Agent."""

from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


class BusyInputMode(str, Enum):
    """Busy input modes."""

    INTERRUPT = "interrupt"  # Default: redirect active turn
    QUEUE = "queue"         # Queue messages
    STEER = "steer"         # Inject into current run


class BusyInputManager:
    """Manage busy input behavior."""

    def __init__(self, mode: BusyInputMode = BusyInputMode.INTERRUPT) -> None:
        self.mode = mode
        self._queue: list[dict] = []
        self._is_busy = False
        self._busy_ack_enabled = True
        self._seen_tip = False

    def set_busy(self, busy: bool) -> None:
        """Set busy state."""
        self._is_busy = busy

    def is_busy(self) -> bool:
        """Check if agent is busy."""
        return self._is_busy

    def handle_input(self, message: dict) -> dict:
        """Handle input based on busy mode.

        Returns:
            Message to process (or None if queued)
        """
        if not self._is_busy:
            return message

        if self.mode == BusyInputMode.INTERRUPT:
            # Return message to redirect
            message["_redirect"] = True
            return message

        elif self.mode == BusyInputMode.QUEUE:
            # Queue for later
            self._queue.append(message)
            return None

        elif self.mode == BusyInputMode.STEER:
            # Inject into current run
            message["_steer"] = True
            return message

        return message

    def get_queued(self) -> list[dict]:
        """Get queued messages."""
        queued = self._queue.copy()
        self._queue.clear()
        return queued

    def get_busy_ack(self) -> str:
        """Get busy acknowledgment message."""
        if not self._busy_ack_enabled:
            return ""

        acks = {
            BusyInputMode.INTERRUPT: "⚡ Agent is busy. Your message will redirect the current task.",
            BusyInputMode.QUEUE: "⏳ Agent is busy. Your message will run after the current task.",
            BusyInputMode.STEER: "🔀 Agent is busy. Your message will be injected into the current task.",
        }
        return acks.get(self.mode, "")

    def get_tip(self) -> str:
        """Get first-time tip."""
        if self._seen_tip:
            return ""

        self._seen_tip = True
        return "💡 Tip: You can change this with `/busy [interrupt|queue|steer]`"

    def set_mode(self, mode: BusyInputMode) -> None:
        """Set the busy input mode."""
        self.mode = mode

    def set_busy_ack_enabled(self, enabled: bool) -> None:
        """Enable/disable busy acknowledgment."""
        self._busy_ack_enabled = enabled
