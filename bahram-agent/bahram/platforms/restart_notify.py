"""
Restart notify.

Public objects: ``RestartNotifier``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class RestartNotifier:
    """
    Restart notifier.
    """

    def __init__(self) -> None:
        """
        Initialise a RestartNotifier instance.
        """
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
        """
        Register platform.

        Args:
            platform (str): platform string.
            notify_fn (Callable): callable used for notify fn.
            home_chat_id (str): home chat id string. Defaults to ``''``.
            enabled (bool): when ``True`` the object is active. Defaults to ``True``.
        """
        self._notify_fns[platform] = notify_fn
        self._enabled[platform] = enabled
        if home_chat_id:
            self._home_chats[platform] = home_chat_id

    async def notify_restart(self, was_interrupted: bool = False) -> None:
        """
        Notify about restart.

        Args:
            was_interrupted (bool): when ``True``, enable was interrupted. Defaults to ``False``.

        Note:
            Coroutine - must be awaited.
        """
        for platform, fn in self._notify_fns.items():
            if not self._enabled.get(platform, True):
                continue

            home_chat = self._home_chats.get(platform, "")
            if not home_chat:
                continue

            try:
                if was_interrupted:
                    message = (
                        "🔄 Bahram Agent restarted after interruption. Send any message to resume."
                    )
                else:
                    message = "✅ Bahram Agent is back online."

                await fn(home_chat, message)
            except Exception as e:
                logger.error(f"Failed to notify {platform}: {e}")

    def set_enabled(self, platform: str, enabled: bool) -> None:
        """
        Set the enabled.

        Args:
            platform (str): platform string.
            enabled (bool): when ``True`` the object is active.
        """
        self._enabled[platform] = enabled

    def set_home_chat(self, platform: str, chat_id: str) -> None:
        """
        Set the home chat.

        Args:
            platform (str): platform string.
            chat_id (str): chat id string.
        """
        self._home_chats[platform] = chat_id
