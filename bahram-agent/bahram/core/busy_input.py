"""
Busy input.

Public objects: ``BusyInputMode``, ``BusyInputManager``.
"""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class BusyInputMode(str, Enum):
    """
    Busy input mode.
    """

    INTERRUPT = "interrupt"
    QUEUE = "queue"
    STEER = "steer"


class BusyInputManager:
    """
    Busy input manager.
    """

    def __init__(self, mode: BusyInputMode = BusyInputMode.INTERRUPT) -> None:
        """
        Initialise a BusyInputManager instance.

        Args:
            mode (BusyInputMode): mode. Defaults to ``BusyInputMode.INTERRUPT``.
        """
        self.mode = mode
        self._queue: list[dict] = []
        self._is_busy = False
        self._busy_ack_enabled = True
        self._seen_tip = False

    def set_busy(self, busy: bool) -> None:
        """
        Set the busy.

        Args:
            busy (bool): when ``True``, enable busy.
        """
        self._is_busy = busy

    def is_busy(self) -> bool:
        """
        Return ``True`` when busy.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        return self._is_busy

    def handle_input(self, message: dict) -> dict:
        """
        Handle input.

        Args:
            message (dict): message to process.

        Returns:
            dict: a mapping of str, Any.
        """
        if not self._is_busy:
            return message

        if self.mode == BusyInputMode.INTERRUPT:
            message["_redirect"] = True
            return message

        elif self.mode == BusyInputMode.QUEUE:
            self._queue.append(message)
            return None

        elif self.mode == BusyInputMode.STEER:
            message["_steer"] = True
            return message

        return message

    def get_queued(self) -> list[dict]:
        """
        Return the queued.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        queued = self._queue.copy()
        self._queue.clear()
        return queued

    def get_busy_ack(self) -> str:
        """
        Return the busy ack.

        Returns:
            str: the rendered string.
        """
        if not self._busy_ack_enabled:
            return ""

        acks = {
            BusyInputMode.INTERRUPT: (
                "⚡ Agent is busy. Your message will redirect the current task."
            ),
            BusyInputMode.QUEUE: "⏳ Agent is busy. Your message will run after the current task.",
            BusyInputMode.STEER: (
                "🔀 Agent is busy. Your message will be injected into the current task."
            ),
        }
        return acks.get(self.mode, "")

    def get_tip(self) -> str:
        """
        Return the tip.

        Returns:
            str: the rendered string.
        """
        if self._seen_tip:
            return ""

        self._seen_tip = True
        return "💡 Tip: You can change this with `/busy [interrupt|queue|steer]`"

    def set_mode(self, mode: BusyInputMode) -> None:
        """
        Set the mode.

        Args:
            mode (BusyInputMode): mode.
        """
        self.mode = mode

    def set_busy_ack_enabled(self, enabled: bool) -> None:
        """
        Set the busy ack enabled.

        Args:
            enabled (bool): when ``True`` the object is active.
        """
        self._busy_ack_enabled = enabled
