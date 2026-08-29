"""Telegram platform integration."""

from __future__ import annotations

import logging
from typing import Any, Optional

from bahram.platforms.base import BasePlatform, PlatformMessage

logger = logging.getLogger(__name__)


class TelegramPlatform(BasePlatform):
    """Telegram bot integration."""

    @property
    def name(self) -> str:
        return "telegram"

    async def start(self) -> None:
        """Start the Telegram bot."""
        try:
            from telegram import Update
            from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

            token = self.config.token
            if not token:
                logger.error("Telegram token not configured")
                return

            self.app = ApplicationBuilder().token(token).build()

            # Add message handler
            self.app.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_update)
            )

            # Start the bot
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()

            logger.info("Telegram bot started")

        except ImportError:
            logger.error("python-telegram-bot not installed. Install with: pip install python-telegram-bot")
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        if hasattr(self, "app"):
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            logger.info("Telegram bot stopped")

    async def send_message(self, chat_id: str, content: str) -> None:
        """Send a message to a Telegram chat."""
        if hasattr(self, "app"):
            await self.app.bot.send_message(chat_id=chat_id, text=content)

    async def reply(self, message: PlatformMessage, content: str) -> None:
        """Reply to a Telegram message."""
        await self.send_message(message.chat_id, content)

    async def _handle_update(self, update: Any, context: Any) -> None:
        """Handle a Telegram update."""
        if not update.message or not update.message.text:
            return

        msg = PlatformMessage(
            platform="telegram",
            user_id=str(update.effective_user.id),
            user_name=update.effective_user.username or "Unknown",
            content=update.message.text,
            chat_id=str(update.effective_chat.id),
            message_id=str(update.message.message_id),
            timestamp=update.message.date.timestamp(),
            reply_to=str(update.message.reply_to_message.message_id)
            if update.message.reply_to_message
            else None,
        )

        await self._handle_message(msg)
