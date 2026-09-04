from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

class SlackAdapter:

    def __init__(self, token: str = "", signing_secret: str = "") -> None:
        self.token = token
        self.signing_secret = signing_secret
        self._app = None
        self._message_fn: Callable | None = None

    def set_message_function(self, fn: Callable) -> None:
        self._message_fn = fn

    async def start(self) -> None:
        if not self.token:
            logger.warning("Slack token not configured")
            return

        try:
            from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
            from slack_bolt.async_app import AsyncApp

            self._app = AsyncApp(token=self.token)

            @self._app.message(".*")
            async def handle_message(message, say):
                if self._message_fn:
                    await self._message_fn(
                        platform="slack",
                        chat_id=message.get("channel", ""),
                        user_id=message.get("user", ""),
                        text=message.get("text", ""),
                        message_id=message.get("ts", ""),
                    )

            handler = AsyncSocketModeHandler(self._app, self.signing_secret)
            await handler.start_async()
            logger.info("Slack adapter started")

        except ImportError:
            logger.warning("slack-bolt not installed")
        except Exception as e:
            logger.error(f"Failed to start Slack adapter: {e}")

    async def send_message(self, chat_id: str, text: str, **kwargs) -> bool:
        if not self._app:
            return False

        try:
            await self._app.client.chat_postMessage(
                channel=chat_id,
                text=text,
                **kwargs,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
            return False

    async def send_dm(self, user_id: str, text: str) -> bool:
        if not self._app:
            return False

        try:

            response = await self._app.client.conversations_open(users=[user_id])
            channel_id = response["channel"]["id"]

            return await self.send_message(channel_id, text)
        except Exception as e:
            logger.error(f"Failed to send Slack DM: {e}")
            return False

    def get_platform_info(self) -> dict[str, Any]:
        return {
            "name": "slack",
            "version": "1.0.0",
            "configured": bool(self.token),
        }
