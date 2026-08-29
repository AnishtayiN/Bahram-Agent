"""Slack platform integration."""

from __future__ import annotations

import logging
from typing import Any

from bahram.platforms.base import BasePlatform, PlatformMessage

logger = logging.getLogger(__name__)


class SlackPlatform(BasePlatform):
    """Slack bot integration."""

    @property
    def name(self) -> str:
        return "slack"

    async def start(self) -> None:
        """Start the Slack bot."""
        try:
            from slack_bolt.async_app import AsyncApp
            from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

            token = self.config.token
            app_token = self.config.app_token

            if not token or not app_token:
                logger.error("Slack tokens not configured")
                return

            self.app = AsyncApp(token=token)

            @self.app.message("")
            async def handle_message(message: dict, say: Any) -> None:
                msg = PlatformMessage(
                    platform="slack",
                    user_id=message.get("user", ""),
                    user_name=message.get("user", ""),
                    content=message.get("text", ""),
                    chat_id=message.get("channel", ""),
                    message_id=message.get("ts", ""),
                    timestamp=float(message.get("ts", 0)),
                    reply_to=message.get("thread_ts"),
                )

                await self._handle_message(msg)

            # Start the app
            handler = AsyncSocketModeHandler(self.app, app_token)
            await handler.start_async()

            logger.info("Slack bot started")

        except ImportError:
            logger.error("slack-bolt not installed. Install with: pip install slack-bolt")
        except Exception as e:
            logger.error(f"Failed to start Slack bot: {e}")

    async def stop(self) -> None:
        """Stop the Slack bot."""
        # Slack doesn't have a direct stop method
        logger.info("Slack bot stopped")

    async def send_message(self, chat_id: str, content: str) -> None:
        """Send a message to a Slack channel."""
        if hasattr(self, "app"):
            await self.app.client.chat_postMessage(channel=chat_id, text=content)

    async def reply(self, message: PlatformMessage, content: str) -> None:
        """Reply to a Slack message."""
        if hasattr(self, "app"):
            await self.app.client.chat_postMessage(
                channel=message.chat_id,
                text=content,
                thread_ts=message.reply_to or message.message_id,
            )
