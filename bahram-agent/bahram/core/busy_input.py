from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)

class BusyInputMode(str, Enum):

    INTERRUPT = "interrupt"
    QUEUE = "queue"
    STEER = "steer"

class BusyInputManager:

    def __init__(self, mode: BusyInputMode = BusyInputMode.INTERRUPT) -> None:
        self.mode = mode
        self._queue: list[dict] = []
        self._is_busy = False
        self._busy_ack_enabled = True
        self._seen_tip = False

    def set_busy(self, busy: bool) -> None:
        self._is_busy = busy

    def is_busy(self) -> bool:
        return self._is_busy

    def handle_input(self, message: dict) -> dict:
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
        queued = self._queue.copy()
        self._queue.clear()
        return queued

    def get_busy_ack(self) -> str:
        if not self._busy_ack_enabled:
            return ""

        acks = {
            BusyInputMode.INTERRUPT: "⚡ Agent is busy. Your message will redirect the current task.",
            BusyInputMode.QUEUE: "⏳ Agent is busy. Your message will run after the current task.",
            BusyInputMode.STEER: "🔀 Agent is busy. Your message will be injected into the current task.",
        }
        return acks.get(self.mode, "")

    def get_tip(self) -> str:
        if self._seen_tip:
            return ""

        self._seen_tip = True
        return "💡 Tip: You can change this with `/busy [interrupt|queue|steer]`"

    def set_mode(self, mode: BusyInputMode) -> None:
        self.mode = mode

    def set_busy_ack_enabled(self, enabled: bool) -> None:
        self._busy_ack_enabled = enabled
