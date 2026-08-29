#!/usr/bin/env python3
"""
Bahram Agent - Telegram Bot
Advanced AI agent with self-improving capabilities
"""

import asyncio
import logging
import os
import sys
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

try:
    from telegram import (
        Update,
        BotCommand,
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        InputMediaPhoto,
        InputMediaDocument,
    )
    from telegram.ext import (
        ApplicationBuilder,
        ContextTypes,
        MessageHandler,
        CommandHandler,
        CallbackQueryHandler,
        ConversationHandler,
        filters,
    )
    from telegram.constants import ParseMode, ChatAction
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False
    print("Error: python-telegram-bot not installed")
    print("Install with: pip install 'python-telegram-bot>=20.0'")
    sys.exit(1)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bahram.core.agent import Agent
from bahram.core.config import Config
from bahram.core.engine import Message, MessageRole

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# States for conversation
WAITING_FOR_MODEL = 1


class BahramTelegramBot:
    """Telegram bot for Bahram Agent."""

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize the bot."""
        self.config = Config.from_file(config_path)
        self.agent: Optional[Agent] = None
        self.sessions: Dict[int, str] = {}  # chat_id -> session_id
        self.user_models: Dict[int, str] = {}  # chat_id -> model
        self.typing_tasks: Dict[int, asyncio.Task] = {}

    async def initialize(self):
        """Initialize the agent."""
        self.agent = Agent(config=self.config)
        await self.agent.start()
        logger.info("Agent initialized")

    async def cleanup(self):
        """Cleanup resources."""
        if self.agent:
            await self.agent.stop()
        logger.info("Cleanup completed")

    def get_session_id(self, chat_id: int) -> str:
        """Get or create session for chat."""
        if chat_id not in self.sessions:
            self.sessions[chat_id] = str(uuid.uuid4())
        return self.sessions[chat_id]

    def get_model(self, chat_id: int) -> str:
        """Get model for chat."""
        return self.user_models.get(chat_id, self.config.agent.model)

    async def send_typing(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send typing indicator."""
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception:
            pass

    async def start_typing_loop(self, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Start continuous typing indicator."""
        async def typing_loop():
            while True:
                await self.send_typing(chat_id, context)
                await asyncio.sleep(4)

        self.typing_tasks[chat_id] = asyncio.create_task(typing_loop())

    async def stop_typing_loop(self, chat_id: int) -> None:
        """Stop typing indicator."""
        task = self.typing_tasks.pop(chat_id, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user = update.effective_user
        keyboard = [
            [
                InlineKeyboardButton("💬 Chat", callback_data="chat"),
                InlineKeyboardButton("📚 Help", callback_data="help"),
            ],
            [
                InlineKeyboardButton("🤖 Models", callback_data="models"),
                InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
            ],
            [
                InlineKeyboardButton("🌐 Web", callback_data="web"),
                InlineKeyboardButton("📊 Status", callback_data="status"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        welcome = (
            f"Welcome <b>{user.first_name}</b>! ☤\n\n"
            "I'm <b>Bahram</b>, your advanced AI assistant.\n\n"
            "Just send me any message and I'll help you with:\n"
            "• 💻 Code writing & analysis\n"
            "• 🌐 Web search & research\n"
            "• 📁 File operations\n"
            "• 🔧 Task automation\n"
            "• And much more...\n\n"
            "Choose an option below or just type a message:"
        )

        await update.message.reply_text(
            welcome,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
        )

    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        help_text = (
            "📖 <b>Bahram Agent - Help</b>\n\n"
            "<b>Commands:</b>\n"
            "/start - Start the bot\n"
            "/help - Show this help\n"
            "/clear - Clear conversation\n"
            "/model - Change AI model\n"
            "/status - Show bot status\n"
            "/feedback - Send feedback\n\n"
            "<b>Features:</b>\n"
            "• Chat with AI\n"
            "• Code analysis\n"
            "• Web search\n"
            "• File operations\n"
            "• Task automation\n\n"
            "<b>Tips:</b>\n"
            "• Send voice messages for transcription\n"
            "• Send images for analysis\n"
            "• Send documents for processing\n"
            "• Use inline buttons for quick actions"
        )

        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

    async def handle_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /clear command."""
        chat_id = update.effective_chat.id

        # Clear session
        if chat_id in self.sessions:
            del self.sessions[chat_id]

        # Clear agent history
        if self.agent:
            session_id = self.get_session_id(chat_id)
            self.agent.clear_history(session_id)

        await update.message.reply_text("✅ Conversation cleared.")

    async def handle_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /model command."""
        if context.args:
            model = context.args[0]
            self.user_models[update.effective_chat.id] = model
            await update.message.reply_text(f"✅ Model changed to: <code>{model}</code>", parse_mode=ParseMode.HTML)
        else:
            keyboard = [
                [
                    InlineKeyboardButton("Claude 3.5", callback_data="model_anthropic/claude-sonnet-4-6"),
                    InlineKeyboardButton("GPT-4o", callback_data="model_openai/gpt-4o"),
                ],
                [
                    InlineKeyboardButton("Hermes 3", callback_data="model_nous/hermes-3-llama-3.1-405b"),
                    InlineKeyboardButton("Gemini", callback_data="model_google/gemini-1.5-pro"),
                ],
                [
                    InlineKeyboardButton("Llama 3.1", callback_data="model_groq/llama-3.1-70b-versatile"),
                    InlineKeyboardButton("Mistral", callback_data="model_mistral/mistral-large-latest"),
                ],
                [InlineKeyboardButton("Cancel", callback_data="cancel")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            current = self.get_model(update.effective_chat.id)
            await update.message.reply_text(
                f"Current model: <code>{current}</code>\n\nSelect a new model:",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )

    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        status = (
            "📊 <b>Bahram Agent Status</b>\n\n"
            f"<b>Version:</b> {self.config.agent.version}\n"
            f"<b>Status:</b> Online ✅\n"
            f"<b>Model:</b> <code>{self.get_model(update.effective_chat.id)}</code>\n"
            f"<b>Session:</b> <code>{self.get_session_id(update.effective_chat.id)[:8]}</code>\n"
            f"<b>Memory:</b> {'✅ Enabled' if self.config.memory.enabled else '❌ Disabled'}\n"
            f"<b>Skills:</b> {'✅ Enabled' if self.config.skills.enabled else '❌ Disabled'}\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        await update.message.reply_text(status, parse_mode=ParseMode.HTML)

    async def handle_feedback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /feedback command."""
        await update.message.reply_text(
            "📝 Send your feedback and I'll forward it to the developers.\n"
            "Just type your message after this command.",
        )

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle callback queries from inline keyboards."""
        query = update.callback_query
        await query.answer()

        data = query.data
        chat_id = query.message.chat.id

        if data == "chat":
            await query.edit_message_text(
                "💬 Just send me any message!\n\n"
                "I can help you with:\n"
                "• Code writing\n"
                "• Web search\n"
                "• File operations\n"
                "• And more..."
            )

        elif data == "help":
            help_text = (
                "📖 <b>Quick Help</b>\n\n"
                "Send any message to chat with me.\n\n"
                "Commands:\n"
                "/start - Start\n"
                "/clear - Clear history\n"
                "/model - Change model\n"
                "/status - Status"
            )
            await query.edit_message_text(help_text, parse_mode=ParseMode.HTML)

        elif data == "models":
            keyboard = [
                [
                    InlineKeyboardButton("Claude 3.5", callback_data="model_anthropic/claude-sonnet-4-6"),
                    InlineKeyboardButton("GPT-4o", callback_data="model_openai/gpt-4o"),
                ],
                [
                    InlineKeyboardButton("Hermes 3", callback_data="model_nous/hermes-3-llama-3.1-405b"),
                    InlineKeyboardButton("Gemini", callback_data="model_google/gemini-1.5-pro"),
                ],
                [InlineKeyboardButton("Back", callback_data="back")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Select a model:", reply_markup=reply_markup)

        elif data == "settings":
            settings = (
                "⚙️ <b>Settings</b>\n\n"
                f"Model: <code>{self.get_model(chat_id)}</code>\n"
                f"Memory: {'On' if self.config.memory.enabled else 'Off'}\n"
                f"Skills: {'On' if self.config.skills.enabled else 'Off'}"
            )
            await query.edit_message_text(settings, parse_mode=ParseMode.HTML)

        elif data == "web":
            await query.edit_message_text(
                "🌐 <b>Web Access</b>\n\n"
                "I can fetch any webpage for you!\n"
                "Just send me a URL.",
                parse_mode=ParseMode.HTML,
            )

        elif data == "status":
            status = f"📊 Status: Online ✅\nModel: {self.get_model(chat_id)}"
            await query.edit_message_text(status)

        elif data == "back":
            keyboard = [
                [
                    InlineKeyboardButton("💬 Chat", callback_data="chat"),
                    InlineKeyboardButton("📚 Help", callback_data="help"),
                ],
                [
                    InlineKeyboardButton("🤖 Models", callback_data="models"),
                    InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Choose an option:", reply_markup=reply_markup)

        elif data.startswith("model_"):
            model = data[6:]
            self.user_models[chat_id] = model
            await query.edit_message_text(f"✅ Model changed to:\n<code>{model}</code>", parse_mode=ParseMode.HTML)

        elif data == "cancel":
            await query.edit_message_text("Cancelled.")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages."""
        if not update.message or not update.message.text:
            return

        chat_id = update.effective_chat.id
        user_message = update.message.text

        # Start typing indicator
        await self.start_typing_loop(chat_id, context)

        try:
            # Get session
            session_id = self.get_session_id(chat_id)
            model = self.get_model(chat_id)

            # Get response
            response = await self.agent.chat(
                user_message,
                session_id=session_id,
                model=model,
            )

            # Stop typing
            await self.stop_typing_loop(chat_id)

            # Send response
            if response.content:
                # Split long messages
                max_length = 4000
                if len(response.content) > max_length:
                    chunks = [response.content[i:i+max_length] for i in range(0, len(response.content), max_length)]
                    for chunk in chunks:
                        await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text(response.content, parse_mode=ParseMode.HTML)

            # Show tool calls if any
            if response.tool_calls:
                tools_used = ", ".join([tc.name for tc in response.tool_calls])
                await update.message.reply_text(f"🔧 Tools used: {tools_used}")

        except Exception as e:
            await self.stop_typing_loop(chat_id)
            logger.error(f"Error handling message: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle voice messages."""
        if not update.message or not update.message.voice:
            return

        chat_id = update.effective_chat.id
        await self.start_typing_loop(chat_id, context)

        try:
            # Download voice
            voice = update.message.voice
            file = await context.bot.get_file(voice.file_id)
            voice_path = f"/tmp/voice_{update.message.message_id}.ogg"
            await file.download_to_drive(voice_path)

            # Process voice (placeholder - in production, use whisper)
            await self.stop_typing_loop(chat_id)
            await update.message.reply_text(
                "🎤 Voice message received!\n\n"
                "Voice transcription will be available soon.\n"
                "Please type your message instead."
            )

            # Cleanup
            os.remove(voice_path)

        except Exception as e:
            await self.stop_typing_loop(chat_id)
            logger.error(f"Error handling voice: {e}")
            await update.message.reply_text(f"❌ Error processing voice: {str(e)}")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle photo messages."""
        if not update.message or not update.message.photo:
            return

        chat_id = update.effective_chat.id
        await self.start_typing_loop(chat_id, context)

        try:
            # Get photo
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            photo_path = f"/tmp/photo_{update.message.message_id}.jpg"
            await file.download_to_drive(photo_path)

            caption = update.message.caption or "What's in this image?"

            # Process image (placeholder)
            await self.stop_typing_loop(chat_id)
            await update.message.reply_text(
                f"🖼️ Image received!\n\n"
                f"Caption: {caption}\n\n"
                "Image analysis will be available soon."
            )

            # Cleanup
            os.remove(photo_path)

        except Exception as e:
            await self.stop_typing_loop(chat_id)
            logger.error(f"Error handling photo: {e}")
            await update.message.reply_text(f"❌ Error processing image: {str(e)}")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle document messages."""
        if not update.message or not update.message.document:
            return

        chat_id = update.effective_chat.id
        await self.start_typing_loop(chat_id, context)

        try:
            # Get document
            document = update.message.document
            file = await context.bot.get_file(document.file_id)
            doc_path = f"/tmp/doc_{document.file_name}"
            await file.download_to_drive(doc_path)

            caption = update.message.caption or "Analyze this document"

            # Process document (placeholder)
            await self.stop_typing_loop(chat_id)
            await update.message.reply_text(
                f"📄 Document received!\n\n"
                f"File: {document.file_name}\n"
                f"Size: {document.file_size} bytes\n"
                f"Caption: {caption}\n\n"
                "Document analysis will be available soon."
            )

            # Cleanup
            os.remove(doc_path)

        except Exception as e:
            await self.stop_typing_loop(chat_id)
            logger.error(f"Error handling document: {e}")
            await update.message.reply_text(f"❌ Error processing document: {str(e)}")

    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle messages containing URLs."""
        if not update.message or not update.message.text:
            return

        chat_id = update.effective_chat.id
        text = update.message.text

        # Check if message contains URL
        import re
        url_pattern = re.compile(r'https?://\S+')
        if url_pattern.search(text):
            await self.start_typing_loop(chat_id, context)

            try:
                # Fetch URL content
                session_id = self.get_session_id(chat_id)
                model = self.get_model(chat_id)

                response = await self.agent.chat(
                    f"Fetch and analyze this URL: {text}",
                    session_id=session_id,
                    model=model,
                )

                await self.stop_typing_loop(chat_id)

                if response.content:
                    await update.message.reply_text(response.content, parse_mode=ParseMode.HTML)

            except Exception as e:
                await self.stop_typing_loop(chat_id)
                logger.error(f"Error handling URL: {e}")
                await update.message.reply_text(f"❌ Error: {str(e)}")


def main():
    """Main entry point."""
    if not HAS_TELEGRAM:
        print("Telegram dependencies not installed.")
        print("Install with: pip install 'python-telegram-bot>=20.0'")
        return

    # Get token
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        print("Set it in .env file or environment variable")
        return

    # Create bot
    bot = BahramTelegramBot()

    # Build application
    app = ApplicationBuilder().token(token).build()

    # Store bot instance
    app.bot_data["bahram_bot"] = bot

    # Add handlers
    app.add_handler(CommandHandler("start", bot.handle_start))
    app.add_handler(CommandHandler("help", bot.handle_help))
    app.add_handler(CommandHandler("clear", bot.handle_clear))
    app.add_handler(CommandHandler("model", bot.handle_model))
    app.add_handler(CommandHandler("status", bot.handle_status))
    app.add_handler(CommandHandler("feedback", bot.handle_feedback))
    app.add_handler(CallbackQueryHandler(bot.handle_callback_query))

    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, bot.handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, bot.handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, bot.handle_document))

    # Set bot commands
    async def post_init(application):
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "Show help"),
            BotCommand("clear", "Clear conversation"),
            BotCommand("model", "Change AI model"),
            BotCommand("status", "Show status"),
        ]
        await application.bot.set_my_commands(commands)

        # Initialize agent
        await bot.initialize()

    async def post_shutdown(application):
        await bot.cleanup()

    app.post_init = post_init
    app.post_shutdown = post_shutdown

    # Run bot
    print("Bot starting...")
    print("Press Ctrl+C to stop")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
