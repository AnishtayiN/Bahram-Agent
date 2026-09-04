from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Optional

logger = logging.getLogger(__name__)

class RestartNotifier:

    def __init__(self) -> None:
        self._notify_fns: dict[str, Callable] = {}
        self._enabled: dict[str, bool] = {}
        self._home_chats: dict[str, str] = {}

    def register_platform(
        self,
        platform: str,
        notify_fn: Callable,
        home_chat_id: str = "",
        enabled: bool = True,
    ) -> None:
        self._notify_fns[platform] = notify_fn
        self._enabled[platform] = enabled
        if home_chat_id:
            self._home_chats[platform] = home_chat_id

    async def notify_restart(self, was_interrupted: bool = False) -> None:
        for platform, fn in self._notify_fns.items():
            if not self._enabled.get(platform, True):
                continue

            home_chat = self._home_chats.get(platform, "")
            if not home_chat:
                continue

            try:
                if was_interrupted:
                    message = "🔄 Bahram Agent restarted after interruption. Send any message to resume."
                else:
                    message = "✅ Bahram Agent is back online."

                await fn(home_chat, message)
            except Exception as e:
                logger.error(f"Failed to notify {platform}: {e}")

    def set_enabled(self, platform: str, enabled: bool) -> None:
        self._enabled[platform] = enabled

    def set_home_chat(self, platform: str, chat_id: str) -> None:
        self._home_chats[platform] = chat_id
