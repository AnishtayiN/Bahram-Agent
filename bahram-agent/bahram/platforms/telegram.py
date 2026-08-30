from __future__ import annotations

import logging
import os
from typing import Any, Callable, Optional

from bahram.platforms.base import BasePlatform, PlatformMessage

logger = logging.getLogger(__name__)

class TelegramPlatform(BasePlatform):
    ""

    def __init__(self, config: Any) -> None:
        super().__init__(config)
        self.app = None
        self.bot = None
        self._agent = None
        self._allowed_users = set(config.allowed_users if hasattr(config, "allowed_users") else [])
        self._chat_sessions: dict[str, str] = {}

    def set_agent(self, agent: Any) -> None:
        self._agent = agent

    @property
    def name(self) -> str:
        return "telegram"

    async def start(self) -> None:
        ""
        try:
            from telegram import Update, BotCommand
            from telegram.ext import (
                ApplicationBuilder,
                ContextTypes,
                MessageHandler,
                CommandHandler,
                filters,
            )

            token = self.config.token
            if not token:
                logger.error("Telegram token not configured")
                return

            self.app = ApplicationBuilder().token(token).build()

            self.app.add_handler(CommandHandler("start", self._handle_start))
            self.app.add_handler(CommandHandler("help", self._handle_help))
            self.app.add_handler(CommandHandler("clear", self._handle_clear))
            self.app.add_handler(CommandHandler("model", self._handle_model))
            self.app.add_handler(CommandHandler("status", self._handle_status))

            self.app.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
            )
            self.app.add_handler(
                MessageHandler(filters.VOICE | filters.AUDIO, self._handle_voice)
            )
            self.app.add_handler(
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, self._handle_image)
            )
            self.app.add_handler(
                MessageHandler(filters.Document.ALL, self._handle_document)
            )

            await self._set_bot_commands()

            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling(drop_pending_updates=True)

            self.bot = self.app.bot
            logger.info("Telegram bot started successfully")

        except ImportError:
            logger.error(
                "python-telegram-bot not installed. Install with: pip install python-telegram-bot"
            )
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")
            raise

    async def stop(self) -> None:
        ""
        if self.app:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            logger.info("Telegram bot stopped")

    async def _set_bot_commands(self) -> None:
        ""
        from telegram import BotCommand

        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Show help message"),
            BotCommand("clear", "Clear conversation history"),
            BotCommand("model", "Change or view current model"),
            BotCommand("status", "Show bot status"),
        ]

        await self.app.bot.set_my_commands(commands)

    async def send_message(self, chat_id: str, content: str, parse_mode: str = "Markdown") -> None:
        ""
        if self.bot:
            try:

                max_length = 4096
                if len(content) > max_length:
                    chunks = [content[i : i + max_length] for i in range(0, len(content), max_length)]
                    for chunk in chunks:
                        await self.bot.send_message(
                            chat_id=chat_id,
                            text=chunk,
                            parse_mode=parse_mode,
                        )
                else:
                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=content,
                        parse_mode=parse_mode,
                    )
            except Exception as e:
                logger.error(f"Failed to send message: {e}")

                await self.bot.send_message(chat_id=chat_id, text=content)

    async def reply(self, message: PlatformMessage, content: str) -> None:
        ""
        await self.send_message(message.chat_id, content)

    async def edit_message(self, chat_id: str, message_id: str, content: str) -> None:
        ""
        if self.bot:
            try:
                await self.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=content,
                )
            except Exception as e:
                logger.error(f"Failed to edit message: {e}")

    async def send_typing(self, chat_id: str) -> None:
        ""
        if self.bot:
            await self.bot.send_chat_action(chat_id=chat_id, action="typing")

    async def send_voice(self, chat_id: str, voice_path: str) -> None:
        ""
        if self.bot:
            with open(voice_path, "rb") as voice:
                await self.bot.send_voice(chat_id=chat_id, voice=voice)

    async def send_document(self, chat_id: str, document_path: str, caption: str = "") -> None:
        ""
        if self.bot:
            with open(document_path, "rb") as doc:
                await self.bot.send_document(
                    chat_id=chat_id,
                    document=doc,
                    caption=caption,
                )

    async def send_photo(self, chat_id: str, photo_path: str, caption: str = "") -> None:
        ""
        if self.bot:
            with open(photo_path, "rb") as photo:
                await self.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=caption,
                )

    def _is_allowed(self, user_id: str) -> bool:
        ""
        if not self._allowed_users:
            return True
        return user_id in self._allowed_users

    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ""
        user_id = str(update.effective_user.id)

        if not self._is_allowed(user_id):
            await update.message.reply_text("Access denied.")
            return

        welcome = (
            "Welcome to Bahram Agent! ☤\n\n"
            "I'm an advanced AI agent with self-improving capabilities.\n\n"
            "Commands:\n"
            "/help - Show help\n"
            "/clear - Clear conversation\n"
            "/model - Change model\n"
            "/status - Show status\n\n"
            "Just send me a message to start chatting!"
        )
        await update.message.reply_text(welcome)

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ""
        help_text = (
            "Bahram Agent Help\n\n"
            "Features:\n"
            "- Chat with AI\n"
            "- Code analysis\n"
            "- Web search\n"
            "- File operations\n"
            "- Task automation\n\n"
            "Commands:\n"
            "/start - Start bot\n"
            "/help - This message\n"
            "/clear - Clear history\n"
            "/model - Change model\n"
            "/status - Bot status\n\n"
            "You can send:\n"
            "- Text messages\n"
            "- Voice messages\n"
            "- Images\n"
            "- Documents\n"
        )
        await update.message.reply_text(help_text)

    async def _handle_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ""

        msg = PlatformMessage(
            platform="telegram",
            user_id=str(update.effective_user.id),
            user_name=update.effective_user.username or "Unknown",
            content="/clear",
            chat_id=str(update.effective_chat.id),
            message_id=str(update.message.message_id),
            timestamp=update.message.date.timestamp(),
        )
        await self._handle_message(msg)
        await update.message.reply_text("Conversation cleared.")

    async def _handle_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ""
        if context.args:
            model = context.args[0]
            msg = PlatformMessage(
                platform="telegram",
                user_id=str(update.effective_user.id),
                user_name=update.effective_user.username or "Unknown",
                content=f"/model {model}",
                chat_id=str(update.effective_chat.id),
                message_id=str(update.message.message_id),
                timestamp=update.message.date.timestamp(),
            )
            await self._handle_message(msg)
            await update.message.reply_text(f"Model changed to: {model}")
        else:
            await update.message.reply_text(
                "Usage: /model <model_name>\n"
                "Example: /model anthropic/claude-sonnet-4-6"
            )

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ""
        status = (
            "Bahram Agent Status\n\n"
            "Version: 1.0.0\n"
            "Status: Online\n"
            "Platform: Telegram\n"
        )
        await update.message.reply_text(status)

    async def _handle_message(self, update_or_message: Any, context: Any = None) -> None:
        ""
        if isinstance(update_or_message, PlatformMessage):
            msg = update_or_message
        else:
            update = update_or_message
            if not update.message or not update.message.text:
                return

            user_id = str(update.effective_user.id)
            if not self._is_allowed(user_id):
                await update.message.reply_text("Access denied.")
                return

            msg = PlatformMessage(
                platform="telegram",
                user_id=user_id,
                user_name=update.effective_user.username or "Unknown",
                content=update.message.text,
                chat_id=str(update.effective_chat.id),
                message_id=str(update.message.message_id),
                timestamp=update.message.date.timestamp(),
                reply_to=str(update.message.reply_to_message.message_id)
                if update.message.reply_to_message
                else None,
            )

        await self._dispatch_to_agent(msg)

    async def _dispatch_to_agent(self, msg: PlatformMessage) -> None:
        if not self._agent:
            logger.warning("No agent wired to Telegram platform")
            await self.send_message(msg.chat_id, "Agent not configured.")
            return

        session_id = self._chat_sessions.get(msg.chat_id)
        chat_id = msg.chat_id

        if msg.content == "/clear":
            if session_id:
                self._agent.clear_history(session_id)
                self._chat_sessions.pop(msg.chat_id, None)
            await self.send_message(chat_id, "Conversation cleared.")
            return

        if msg.content.startswith("/model "):
            model = msg.content.split(" ", 1)[1].strip()
            await self.send_message(chat_id, f"Model set to: {model}")
            return

        if msg.content == "/status":
            status = "Online"
            if self._agent._budget_manager:
                usage = self._agent._budget_manager.get_all_usage()
                total_tokens = sum(
                    r.get("total_tokens", 0)
                    for r in usage.get("runs", {}).values()
                )
                status += f"\nBudget: {total_tokens} tokens used"
            await self.send_message(chat_id, f"Bahram Agent Status\n\nVersion: 1.0.0\nStatus: {status}")
            return

        await self.send_typing(chat_id)

        try:
            response = await self._agent.run(
                message=msg.content,
                session_id=session_id,
            )
            await self.send_message(chat_id, response.content)
        except Exception as e:
            logger.error(f"Agent error: {e}")
            await self.send_message(chat_id, f"Error: {str(e)[:200]}")

    async def _handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ""
        if not update.message:
            return

        user_id = str(update.effective_user.id)
        if not self._is_allowed(user_id):
            await update.message.reply_text("Access denied.")
            return

        voice = update.message.voice or update.message.audio
        if voice:
            file = await context.bot.get_file(voice.file_id)
            voice_path = f"/tmp/voice_{update.message.message_id}.ogg"
            await file.download_to_drive(voice_path)

            msg = PlatformMessage(
                platform="telegram",
                user_id=user_id,
                user_name=update.effective_user.username or "Unknown",
                content=f"[Voice message: {voice_path}]",
                chat_id=str(update.effective_chat.id),
                message_id=str(update.message.message_id),
                timestamp=update.message.date.timestamp(),
                metadata={"voice_path": voice_path},
            )

            await self._handle_message(msg)

    async def _handle_image(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ""
        if not update.message:
            return

        user_id = str(update.effective_user.id)
        if not self._is_allowed(user_id):
            await update.message.reply_text("Access denied.")
            return

        photos = update.message.photo
        if photos:
            photo = photos[-1]
            file = await context.bot.get_file(photo.file_id)
            photo_path = f"/tmp/photo_{update.message.message_id}.jpg"
            await file.download_to_drive(photo_path)

            caption = update.message.caption or ""
            msg = PlatformMessage(
                platform="telegram",
                user_id=user_id,
                user_name=update.effective_user.username or "Unknown",
                content=f"[Image: {photo_path}] {caption}",
                chat_id=str(update.effective_chat.id),
                message_id=str(update.message.message_id),
                timestamp=update.message.date.timestamp(),
                metadata={"photo_path": photo_path, "caption": caption},
            )

            await self._handle_message(msg)

    async def _handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ""
        if not update.message or not update.message.document:
            return

        user_id = str(update.effective_user.id)
        if not self._is_allowed(user_id):
            await update.message.reply_text("Access denied.")
            return

        document = update.message.document
        file = await context.bot.get_file(document.file_id)
        doc_path = f"/tmp/doc_{document.file_name}"
        await file.download_to_drive(doc_path)

        caption = update.message.caption or ""
        msg = PlatformMessage(
            platform="telegram",
            user_id=user_id,
            user_name=update.effective_user.username or "Unknown",
            content=f"[Document: {doc_path}] {caption}",
            chat_id=str(update.effective_chat.id),
            message_id=str(update.message.message_id),
            timestamp=update.message.date.timestamp(),
            metadata={"document_path": doc_path, "file_name": document.file_name},
        )

        await self._handle_message(msg)
