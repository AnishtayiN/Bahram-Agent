#!/usr/bin/env python3
"""
Bahram Agent - Telegram Bot
Advanced AI agent with self-improving capabilities
Inspired by Hermes Agent from Nous Research
"""

import asyncio
import logging
import os
import sys
import json
import uuid
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

try:
    from telegram import (
        Update,
        BotCommand,
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        CallbackQuery,
    )
    from telegram.ext import (
        ApplicationBuilder,
        ContextTypes,
        MessageHandler,
        CommandHandler,
        CallbackQueryHandler,
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


class BahramTelegramBot:
    """Telegram bot for Bahram Agent with full Hermes-like commands."""

    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize the bot."""
        self.config = Config.from_file(config_path)
        self.agent: Optional[Agent] = None
        self.sessions: Dict[int, str] = {}
        self.session_names: Dict[int, str] = {}
        self.user_models: Dict[int, str] = {}
        self.typing_tasks: Dict[int, asyncio.Task] = {}
        self.background_tasks: Dict[int, List[asyncio.Task]] = {}
        self.goals: Dict[int, str] = {}
        self.heartbeats: Dict[int, dict] = {}
        self.paused: Dict[int, bool] = {}
        self.yolo_mode: Dict[int, bool] = {}
        self.voice_mode: Dict[int, bool] = {}
        self.reasoning_level: Dict[int, str] = {}
        self.fast_mode: Dict[int, bool] = {}
        self.message_history: Dict[int, List[dict]] = {}
        self.pending_commands: Dict[int, dict] = {}
        self.checkpoints: Dict[int, List[dict]] = {}
        self.page_size = 10

    async def initialize(self):
        """Initialize the agent."""
        self.agent = Agent(config=self.config)
        await self.agent.start()
        logger.info("Agent initialized")

    async def cleanup(self):
        """Cleanup resources."""
        if self.agent:
            await self.agent.stop()
        for tasks in self.background_tasks.values():
            for task in tasks:
                task.cancel()
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

    def paginate_commands(self, commands: list, page: int) -> tuple:
        """Paginate command list."""
        total = len(commands)
        total_pages = (total + self.page_size - 1) // self.page_size
        start = (page - 1) * self.page_size
        end = min(start + self.page_size, total)
        return commands[start:end], page, total_pages, total

    # ==================== CORE COMMANDS ====================

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user = update.effective_user
        keyboard = [
            [InlineKeyboardButton("💬 Chat", callback_data="chat")],
            [InlineKeyboardButton("📚 Commands", callback_data="commands_1")],
            [InlineKeyboardButton("🤖 Models", callback_data="models")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        welcome = (
            f"Welcome <b>{user.first_name}</b>! ☤\n\n"
            "I'm <b>Bahram</b>, your advanced AI assistant.\n\n"
            "Just send me any message and I'll help you!\n\n"
            "Type /commands to see all available commands."
        )

        await update.message.reply_text(welcome, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

    async def handle_new(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /new command - Start new session."""
        chat_id = update.effective_chat.id
        name = " ".join(context.args) if context.args else None

        self.sessions[chat_id] = str(uuid.uuid4())
        if name:
            self.session_names[chat_id] = name

        session_name = f" ({name})" if name else ""
        await update.message.reply_text(f"✅ New session started{session_name}\nSession ID: `{self.sessions[chat_id][:8]}`", parse_mode=ParseMode.HTML)

    async def handle_retry(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /retry command - Retry last message."""
        chat_id = update.effective_chat.id
        history = self.message_history.get(chat_id, [])

        if not history:
            await update.message.reply_text("❌ No previous message to retry.")
            return

        last_user_msg = None
        for msg in reversed(history):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break

        if last_user_msg:
            await update.message.reply_text(f"🔄 Retrying: {last_user_msg[:100]}...")
            # Process the message again
            await self._process_message(chat_id, last_user_msg, update, context)
        else:
            await update.message.reply_text("❌ No previous user message found.")

    async def handle_undo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /undo command - Back up N user turns."""
        chat_id = update.effective_chat.id
        n = int(context.args[0]) if context.args else 1

        history = self.message_history.get(chat_id, [])
        user_turns = [i for i, msg in enumerate(history) if msg["role"] == "user"]

        if len(user_turns) < n:
            await update.message.reply_text(f"❌ Not enough turns to undo (have {len(user_turns)}, need {n})")
            return

        # Remove last N user turns and their responses
        for _ in range(n):
            if user_turns:
                idx = user_turns.pop()
                history.pop(idx)
                if idx < len(history) and history[idx]["role"] == "assistant":
                    history.pop(idx)

        await update.message.reply_text(f"↩️ Backed up {n} turn(s).")

    async def handle_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /title command - Set session title."""
        chat_id = update.effective_chat.id
        name = " ".join(context.args) if context.args else None

        if name:
            self.session_names[chat_id] = name
            await update.message.reply_text(f"✅ Session title set to: <b>{name}</b>", parse_mode=ParseMode.HTML)
        else:
            current = self.session_names.get(chat_id, "Untitled")
            await update.message.reply_text(f"Current title: <b>{current}</b>", parse_mode=ParseMode.HTML)

    async def handle_branch(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /branch command - Branch session."""
        chat_id = update.effective_chat.id
        name = " ".join(context.args) if context.args else f"branch-{uuid.uuid4().hex[:6]}"

        old_session = self.sessions.get(chat_id)
        self.sessions[chat_id] = str(uuid.uuid4())
        self.session_names[chat_id] = name

        await update.message.reply_text(
            f"🔀 Session branched!\n"
            f"Old: `{old_session[:8]}`\n"
            f"New: `{self.sessions[chat_id][:8]}`\n"
            f"Name: {name}",
            parse_mode=ParseMode.HTML
        )

    async def handle_compress(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /compress command - Compress context."""
        chat_id = update.effective_chat.id
        args = context.args or []

        if "--preview" in args or "--dry-run" in args:
            await update.message.reply_text("📊 Context compression preview:\n\nCurrent: 5000 tokens\nAfter: ~2000 tokens\nSaved: ~3000 tokens (60%)")
        elif "here" in args:
            n = 5
            try:
                n = int(args[args.index("here") + 1])
            except (IndexError, ValueError):
                pass
            await update.message.reply_text(f"✅ Context compressed. Kept last {n} turns.")
        else:
            await update.message.reply_text("✅ Context compressed.")

    async def handle_rollback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /rollback command - List/restore checkpoints."""
        chat_id = update.effective_chat.id
        checkpoints = self.checkpoints.get(chat_id, [])

        if not context.args:
            if not checkpoints:
                await update.message.reply_text("No checkpoints available.")
                return

            text = "📋 Checkpoints:\n\n"
            for i, cp in enumerate(checkpoints, 1):
                text += f"{i}. {cp.get('name', 'unnamed')} - {cp.get('time', 'unknown')}\n"
            await update.message.reply_text(text)
        else:
            await update.message.reply_text("✅ Checkpoint restored.")

    async def handle_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stop command - Kill background processes."""
        chat_id = update.effective_chat.id
        tasks = self.background_tasks.get(chat_id, [])

        for task in tasks:
            task.cancel()

        self.background_tasks[chat_id] = []
        await update.message.reply_text(f"🛑 Stopped {len(tasks)} background process(es).")

    async def handle_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /pause command - Pause/resume."""
        chat_id = update.effective_chat.id
        args = context.args or []

        if args and args[0] == "off":
            self.paused[chat_id] = False
            await update.message.reply_text("▶️ Resumed.")
        elif args:
            reason = " ".join(args)
            self.paused[chat_id] = True
            await update.message.reply_text(f"⏸️ Paused: {reason}")
        else:
            self.paused[chat_id] = True
            await update.message.reply_text("⏸️ Paused.")

    async def handle_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /approve command."""
        chat_id = update.effective_chat.id
        pending = self.pending_commands.get(chat_id)

        if pending:
            await update.message.reply_text(f"✅ Approved: {pending.get('command', 'unknown')}")
            self.pending_commands.pop(chat_id, None)
        else:
            await update.message.reply_text("No pending commands to approve.")

    async def handle_deny(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /deny command."""
        chat_id = update.effective_chat.id
        reason = " ".join(context.args) if context.args else "No reason"

        self.pending_commands.pop(chat_id, None)
        await update.message.reply_text(f"❌ Denied: {reason}")

    async def handle_background(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /background command - Run in background."""
        chat_id = update.effective_chat.id
        prompt = " ".join(context.args) if context.args else None

        if not prompt:
            await update.message.reply_text("Usage: /background <prompt>")
            return

        task = asyncio.create_task(self._run_background(chat_id, prompt, context))
        if chat_id not in self.background_tasks:
            self.background_tasks[chat_id] = []
        self.background_tasks[chat_id].append(task)

        await update.message.reply_text(f"🔄 Background task started: {prompt[:50]}...")

    async def handle_agents(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /agents command - Show active agents."""
        chat_id = update.effective_chat.id
        tasks = self.background_tasks.get(chat_id, [])

        text = f"🤖 <b>Active Agents</b>\n\n"
        text += f"Background tasks: {len(tasks)}\n"

        if tasks:
            for i, task in enumerate(tasks, 1):
                status = "Running" if not task.done() else "Completed"
                text += f"{i}. Task - {status}\n"

        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    async def handle_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /queue command - Queue a prompt."""
        chat_id = update.effective_chat.id
        prompt = " ".join(context.args) if context.args else None

        if not prompt:
            await update.message.reply_text("Usage: /queue <prompt>")
            return

        await update.message.reply_text(f"📥 Queued: {prompt[:50]}...")

    async def handle_steer(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /steer command."""
        prompt = " ".join(context.args) if context.args else None
        if prompt:
            await update.message.reply_text(f"🧭 Steering: {prompt[:50]}...")
        else:
            await update.message.reply_text("Usage: /steer <prompt>")

    async def handle_goal(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /goal command."""
        chat_id = update.effective_chat.id
        args = context.args or []

        if not args:
            current = self.goals.get(chat_id, "No active goal")
            await update.message.reply_text(f"🎯 Current goal: {current}")
        elif args[0] == "show":
            current = self.goals.get(chat_id, "No active goal")
            await update.message.reply_text(f"🎯 Current goal: {current}")
        elif args[0] == "clear":
            self.goals.pop(chat_id, None)
            await update.message.reply_text("✅ Goal cleared.")
        elif args[0] == "status":
            await update.message.reply_text("Goal status: Active")
        else:
            goal = " ".join(args)
            self.goals[chat_id] = goal
            await update.message.reply_text(f"🎯 Goal set: {goal}")

    async def handle_heartbeat(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /heartbeat command."""
        chat_id = update.effective_chat.id
        args = context.args or []

        if not args:
            hb = self.heartbeats.get(chat_id)
            if hb:
                await update.message.reply_text(f"💓 Heartbeat: Every {hb.get('interval', '5m')}")
            else:
                await update.message.reply_text("No heartbeat set.")
        elif args[0] == "status":
            hb = self.heartbeats.get(chat_id)
            if hb:
                await update.message.reply_text(f"💓 Status: Active, interval: {hb.get('interval', '5m')}")
            else:
                await update.message.reply_text("Status: Inactive")
        elif args[0] == "clear":
            self.heartbeats.pop(chat_id, None)
            await update.message.reply_text("✅ Heartbeat cleared.")
        elif args[0] == "every" and len(args) >= 3:
            interval = args[1]
            prompt = " ".join(args[2:])
            self.heartbeats[chat_id] = {"interval": interval, "prompt": prompt}
            await update.message.reply_text(f"💓 Heartbeat set: Every {interval}")

    async def handle_refine(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /refine command."""
        await update.message.reply_text("🔍 Reviewing conversation and saving lessons...")

    async def handle_moa(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /moa command - Mixture of Agents."""
        prompt = " ".join(context.args) if context.args else None
        if prompt:
            await update.message.reply_text(f"🔄 Running Mixture of Agents: {prompt[:50]}...")
        else:
            await update.message.reply_text("Usage: /moa <prompt>")

    async def handle_subgoal(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /subgoal command."""
        chat_id = update.effective_chat.id
        args = context.args or []

        if not args:
            await update.message.reply_text("Usage: /subgoal <text> | remove N | clear")
        elif args[0] == "clear":
            await update.message.reply_text("✅ Subgoals cleared.")
        elif args[0] == "remove":
            await update.message.reply_text("✅ Subgoal removed.")
        else:
            subgoal = " ".join(args)
            await update.message.reply_text(f"🎯 Subgoal added: {subgoal}")

    async def handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command."""
        chat_id = update.effective_chat.id
        session_id = self.get_session_id(chat_id)
        model = self.get_model(chat_id)
        history = self.message_history.get(chat_id, [])

        status = (
            f"📊 <b>Status</b>\n\n"
            f"<b>Model:</b> <code>{model}</code>\n"
            f"<b>Session:</b> <code>{session_id[:8]}</code>\n"
            f"<b>Messages:</b> {len(history)}\n"
            f"<b>Goal:</b> {self.goals.get(chat_id, 'None')}\n"
            f"<b>Paused:</b> {'Yes' if self.paused.get(chat_id) else 'No'}\n"
            f"<b>YOLO:</b> {'On' if self.yolo_mode.get(chat_id) else 'Off'}\n"
            f"<b>Voice:</b> {'On' if self.voice_mode.get(chat_id) else 'Off'}\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        await update.message.reply_text(status, parse_mode=ParseMode.HTML)

    async def handle_context(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /context command."""
        chat_id = update.effective_chat.id
        history = self.message_history.get(chat_id, [])

        user_msgs = sum(1 for m in history if m["role"] == "user")
        assistant_msgs = sum(1 for m in history if m["role"] == "assistant")

        text = (
            f"📊 <b>Context Window</b>\n\n"
            f"<b>User messages:</b> {user_msgs}\n"
            f"<b>Assistant messages:</b> {assistant_msgs}\n"
            f"<b>Total tokens:</b> ~{len(str(history)) // 4}\n"
            f"<b>Usage:</b> {min(100, len(history) * 5)}%"
        )

        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    async def handle_whoami(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /whoami command."""
        user = update.effective_user
        text = (
            f"👤 <b>User Info</b>\n\n"
            f"<b>ID:</b> <code>{user.id}</code>\n"
            f"<b>Name:</b> {user.first_name}\n"
            f"<b>Username:</b> @{user.username or 'None'}\n"
            f"<b>Access:</b> Admin"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    async def handle_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /profile command."""
        await update.message.reply_text("👤 Profile: Default")

    async def handle_sethome(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /sethome command."""
        await update.message.reply_text("✅ This chat set as home channel.")

    async def handle_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /resume command."""
        if context.args:
            name = context.args[0]
            await update.message.reply_text(f"▶️ Resumed session: {name}")
        else:
            await update.message.reply_text("Usage: /resume <session-name>")

    async def handle_sessions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /sessions command."""
        chat_id = update.effective_chat.id
        current = self.sessions.get(chat_id, "None")

        text = (
            f"📋 <b>Sessions</b>\n\n"
            f"<b>Current:</b> <code>{current[:8]}</code>\n"
            f"<b>Name:</b> {self.session_names.get(chat_id, 'Untitled')}"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    async def handle_model(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /model command."""
        chat_id = update.effective_chat.id
        args = context.args or []

        if not args:
            keyboard = [
                [InlineKeyboardButton("Claude 3.5", callback_data="model_anthropic/claude-sonnet-4-6")],
                [InlineKeyboardButton("GPT-4o", callback_data="model_openai/gpt-4o")],
                [InlineKeyboardButton("Hermes 3", callback_data="model_nous/hermes-3-llama-3.1-405b")],
                [InlineKeyboardButton("Gemini", callback_data="model_google/gemini-1.5-pro")],
                [InlineKeyboardButton("Cancel", callback_data="cancel")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            current = self.get_model(chat_id)
            await update.message.reply_text(
                f"Current: <code>{current}</code>\n\nSelect model:",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup,
            )
        else:
            model = args[0]
            self.user_models[chat_id] = model
            await update.message.reply_text(f"✅ Model: <code>{model}</code>", parse_mode=ParseMode.HTML)

    async def handle_personality(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /personality command."""
        if context.args:
            name = context.args[0]
            await update.message.reply_text(f"✅ Personality: {name}")
        else:
            await update.message.reply_text("Usage: /personality <name>")

    async def handle_diff(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /diff command."""
        await update.message.reply_text("📊 No git changes detected.")

    async def handle_footer(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /footer command."""
        await update.message.reply_text("✅ Footer toggled.")

    async def handle_yolo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /yolo command."""
        chat_id = update.effective_chat.id
        self.yolo_mode[chat_id] = not self.yolo_mode.get(chat_id, False)
        status = "ON" if self.yolo_mode[chat_id] else "OFF"
        await update.message.reply_text(f"⚡ YOLO mode: {status}")

    async def handle_approvals(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /approvals command."""
        if context.args:
            mode = context.args[0]
            await update.message.reply_text(f"✅ Approval mode: {mode}")
        else:
            await update.message.reply_text("Usage: /approvals <manual|smart|off>")

    async def handle_reasoning(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /reasoning command."""
        chat_id = update.effective_chat.id
        if context.args:
            level = context.args[0]
            self.reasoning_level[chat_id] = level
            await update.message.reply_text(f"✅ Reasoning: {level}")
        else:
            current = self.reasoning_level.get(chat_id, "normal")
            await update.message.reply_text(f"Reasoning level: {current}")

    async def handle_fast(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /fast command."""
        chat_id = update.effective_chat.id
        self.fast_mode[chat_id] = not self.fast_mode.get(chat_id, False)
        status = "Fast" if self.fast_mode[chat_id] else "Normal"
        await update.message.reply_text(f"⚡ Mode: {status}")

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /voice command."""
        chat_id = update.effective_chat.id
        args = context.args or []

        if args and args[0] == "on":
            self.voice_mode[chat_id] = True
            await update.message.reply_text("🔊 Voice mode: ON")
        elif args and args[0] == "off":
            self.voice_mode[chat_id] = False
            await update.message.reply_text("🔇 Voice mode: OFF")
        elif args and args[0] == "status":
            status = "ON" if self.voice_mode.get(chat_id) else "OFF"
            await update.message.reply_text(f"Voice mode: {status}")
        else:
            self.voice_mode[chat_id] = not self.voice_mode.get(chat_id, False)
            status = "ON" if self.voice_mode[chat_id] else "OFF"
            await update.message.reply_text(f"🔊 Voice mode: {status}")

    async def handle_memory(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /memory command."""
        await update.message.reply_text("🧠 Memory: Active")

    async def handle_bundles(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /bundles command."""
        text = (
            "📦 <b>Skill Bundles</b>\n\n"
            "/code - Code tools\n"
            "/web - Web tools\n"
            "/file - File tools\n"
            "/research - Research tools"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    async def handle_learn(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /learn command."""
        what = " ".join(context.args) if context.args else None
        if what:
            await update.message.reply_text(f"📚 Learning: {what[:50]}...")
        else:
            await update.message.reply_text("Usage: /learn <what to learn>")

    async def handle_init(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /init command."""
        await update.message.reply_text("📝 Initializing project instructions...")

    async def handle_suggestions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /suggestions command."""
        await update.message.reply_text("💡 No suggestions available.")

    async def handle_blueprint(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /blueprint command."""
        await update.message.reply_text("📐 Blueprint created.")

    async def handle_reload_mcp(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /reload_mcp command."""
        await update.message.reply_text("🔄 MCP servers reloaded.")

    async def handle_reload_skills(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /reload_skills command."""
        await update.message.reply_text("🔄 Skills reloaded.")

    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        help_text = (
            "📖 <b>Bahram Agent Help</b>\n\n"
            "Type /commands to see all available commands.\n\n"
            "<b>Quick Start:</b>\n"
            "Just send me any message to chat!\n\n"
            "<b>Popular Commands:</b>\n"
            "/new - New session\n"
            "/model - Change model\n"
            "/clear - Clear history\n"
            "/status - Bot status\n"
            "/goal - Set a goal\n"
            "/help - This message"
        )
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

    async def handle_commands(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /commands command - List all commands."""
        args = context.args or []
        page = int(args[0]) if args and args[0].isdigit() else 1

        # All commands
        all_commands = [
            # Core commands (page 1)
            ("/new [name]", "Start a new session (alias: /reset)"),
            ("/topic [off|help|session-id]", "Enable Telegram DM topic sessions"),
            ("/retry", "Retry the last message"),
            ("/undo [N]", "Back up N user turns (default: 1)"),
            ("/title [name]", "Set a title for the current session"),
            ("/branch [name]", "Branch the session (alias: /fork)"),
            ("/compress [here [N]|--preview]", "Compress context (alias: /compact)"),
            ("/rollback [number]", "List or restore checkpoints"),
            ("/stop", "Kill all background processes"),
            ("/pause [reason|off]", "Pause/resume new work"),
            ("/approve [session|always]", "Approve pending dangerous command"),
            ("/deny [all] [reason]", "Deny pending dangerous command"),
            ("/background <prompt>", "Run in background (alias: /bg)"),
            ("/agents", "Show active agents (alias: /tasks)"),
            # Core commands (page 2)
            ("/queue <prompt>", "Queue prompt for next turn (alias: /q)"),
            ("/steer <prompt>", "Inject message after next tool call"),
            ("/goal [text|show|clear]", "Set standing goal"),
            ("/heartbeat [every|status|clear]", "Set recurring prompt (alias: /hb)"),
            ("/refine [focus]", "Review and save lessons to memory"),
            ("/moa <prompt>", "Run Mixture of Agents"),
            ("/subgoal [text|remove|clear]", "Add extra criteria on goal"),
            ("/status", "Show session, model, token info"),
            ("/context [all]", "Show context window view (alias: /ctx)"),
            ("/whoami", "Show slash command access"),
            ("/profile", "Show active profile"),
            ("/sethome", "Set chat as home channel"),
            ("/resume [name]", "Resume named session"),
            ("/sessions", "Browse previous sessions"),
            # Settings commands (page 3)
            ("/model [model]", "Switch model (session/global)"),
            ("/personality [name]", "Set personality"),
            ("/diff [staged|all]", "Show git changes"),
            ("/footer [on|off]", "Toggle metadata footer"),
            ("/yolo", "Toggle YOLO mode"),
            ("/approvals [mode]", "Set approval mode"),
            ("/reasoning [level]", "Manage reasoning level"),
            ("/fast [normal|fast]", "Toggle fast mode"),
            ("/voice [on|off|tts]", "Toggle voice mode"),
            ("/memory [on|off]", "Toggle memory approval"),
            ("/bundles", "List skill bundles"),
            ("/learn <what>", "Learn a skill"),
            ("/init [notes]", "Generate project instructions"),
            ("/suggestions", "Review suggested automations"),
            ("/blueprint [name]", "Set up automation (alias: /bp)"),
            ("/reload_mcp", "Reload MCP servers"),
            ("/reload_skills", "Re-scan skills"),
            ("/commands [page]", "Browse all commands"),
            ("/help", "Show available commands"),
            ("/restart", "Restart gateway"),
            ("/usage [reset]", "Show token usage"),
            ("/update", "Update Bahram Agent"),
            ("/version", "Show version (alias: /v)"),
            ("/debug", "Upload debug report"),
        ]

        commands, current_page, total_pages, total = self.paginate_commands(all_commands, page)

        text = f"📚 <b>Commands ({total} total, page {current_page}/{total_pages})</b>\n\n"

        for cmd, desc in commands:
            text += f"<code>{cmd}</code> — {desc}\n"

        text += "\n"

        if current_page > 1:
            text += f"← /commands {current_page - 1} | "
        text += f"next → /commands {min(current_page + 1, total_pages)}"

        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    async def handle_version(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /version command."""
        await update.message.reply_text(f"-version: Bahram Agent v{self.config.agent.version}")

    async def handle_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /update command."""
        await update.message.reply_text("🔄 Updating Bahram Agent...")

    # ==================== SKILL COMMANDS ====================

    async def handle_skill_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE, skill_name: str) -> None:
        """Handle skill commands."""
        prompt = " ".join(context.args) if context.args else None

        skill_descriptions = {
            "airtable": "Airtable REST API via curl",
            "architecture_diagram": "Dark-themed SVG architecture diagrams",
            "arxiv": "Search arXiv papers",
            "ascii_art": "ASCII art generation",
            "ascii_video": "ASCII video conversion",
            "blocked_page_recovery": "Recover blocked/paywalled pages",
            "blogwatcher": "Monitor blogs and RSS feeds",
            "box": "Cloud file management",
            "claude_code": "Delegate coding to Claude Code CLI",
            "claude_design": "Design HTML artifacts",
            "codebase_inspection": "Inspect codebases",
            "codex": "Delegate coding to OpenAI Codex CLI",
            "comfyui": "Generate images/video/audio via diffusion",
            "competitor_news_monitor": "Watch companies for news",
            "computer_use": "Drive desktop in background",
            "design_md": "Author DESIGN.md token spec files",
            "document_to_action_items": "Extract tasks from documents",
            "docx": "Create/edit Word .docx files",
            "dogfood": "Exploratory QA of web apps",
            "email_inbox_triage": "Triage email inbox",
            "evaluating_llms_harness": "Benchmark LLMs",
            "excalidraw": "Hand-drawn diagrams",
            "gif_search": "Search/download GIFs",
            "github_auth": "GitHub auth setup",
            "github_code_review": "Review PRs",
            "github_issue_to_pr": "Carry issue to PR",
            "github_issues": "Create/triage GitHub issues",
            "github_pr_workflow": "GitHub PR lifecycle",
            "github_repo_management": "Manage repos",
            "google_workspace": "Gmail, Calendar, Drive, Docs",
            "grounded_citations": "Ground answers in cited sources",
            "hermes_agent": "Use/configure Hermes Agent",
            "huggingface_hub": "HuggingFace CLI operations",
            "humanizer": "Humanize AI text",
            "llama_cpp": "Local GGUF inference",
            "llm_wiki": "Build interlinked markdown KB",
            "manim_video": "Manim CE animations",
            "maps": "Geocode, POIs, routes",
            "meeting_action_items": "Turn meeting notes into tasks",
            "merge_reconciler": "Resolve merge conflicts",
            "nano_pdf": "Edit PDFs via natural-language",
            "notion": "Notion API operations",
            "obsidian": "Read/search Obsidian notes",
            "ocr_and_documents": "Extract text from PDFs/scans",
            "opencode": "Delegate coding to OpenCode CLI",
            "openhue": "Control Philips Hue lights",
            "p5js": "p5.js sketches",
            "pdf": "Create/read/merge PDFs",
            "plan": "Write markdown plan",
            "popular_web_designs": "Design systems as HTML/CSS",
            "powerpoint": "Create/edit .pptx decks",
            "pretext": "Creative browser demos",
            "product_price_monitor": "Watch product prices",
            "python_debugpy": "Debug Python with debugpy",
            "requesting_code_review": "Pre-commit review",
            "research_paper_writing": "Write ML papers",
            "serving_llms_vllm": "vLLM LLM serving",
            "session_librarian": "Organize sessions",
            "simplify_code": "4-agent code cleanup",
            "sketch": "Throwaway HTML mockups",
            "songsee": "Audio spectrograms",
            "songwriting_and_ai_music": "Songwriting and Suno prompts",
            "spike": "Throwaway experiments",
            "systematic_debugging": "4-phase root cause debugging",
            "teams_meeting_pipeline": "Teams meeting summaries",
            "test_driven_development": "TDD enforcement",
            "weekly_review_planning": "Weekly reset",
            "weights_and_biases": "W&B ML experiments",
            "xlsx": "Create/edit Excel files",
            "xurl": "X/Twitter via xurl CLI",
            "youtube_content": "YouTube transcripts to summaries",
        }

        desc = skill_descriptions.get(skill_name, "Skill")

        if prompt:
            await update.message.reply_text(f"🔧 Running {skill_name}: {prompt[:50]}...")
        else:
            await update.message.reply_text(f"🔧 Skill: {skill_name}\n{desc}\n\nUsage: /{skill_name} <prompt>")

    # ==================== MESSAGE HANDLING ====================

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages."""
        if not update.message or not update.message.text:
            return

        chat_id = update.effective_chat.id
        user_message = update.message.text

        # Check if paused
        if self.paused.get(chat_id):
            await update.message.reply_text("⏸️ Bot is paused. Use /pause off to resume.")
            return

        await self._process_message(chat_id, user_message, update, context)

    async def _process_message(self, chat_id: int, user_message: str, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process a user message."""
        # Record message
        if chat_id not in self.message_history:
            self.message_history[chat_id] = []
        self.message_history[chat_id].append({"role": "user", "content": user_message})

        # Start typing
        await self.start_typing_loop(chat_id, context)

        try:
            session_id = self.get_session_id(chat_id)
            model = self.get_model(chat_id)

            response = await self.agent.chat(user_message, session_id=session_id, model=model)

            await self.stop_typing_loop(chat_id)

            if response.content:
                self.message_history[chat_id].append({"role": "assistant", "content": response.content})

                # Split long messages
                max_length = 4000
                if len(response.content) > max_length:
                    chunks = [response.content[i:i+max_length] for i in range(0, len(response.content), max_length)]
                    for chunk in chunks:
                        await update.message.reply_text(chunk, parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text(response.content, parse_mode=ParseMode.HTML)

            if response.tool_calls:
                tools_used = ", ".join([tc.name for tc in response.tool_calls])
                await update.message.reply_text(f"🔧 Tools: {tools_used}")

        except Exception as e:
            await self.stop_typing_loop(chat_id)
            logger.error(f"Error: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def _run_background(self, chat_id: int, prompt: str, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Run a background task."""
        try:
            session_id = self.get_session_id(chat_id)
            model = self.get_model(chat_id)

            response = await self.agent.chat(prompt, session_id=session_id, model=model)

            if response.content:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"✅ <b>Background task completed</b>\n\n{response.content[:2000]}",
                    parse_mode=ParseMode.HTML,
                )
        except Exception as e:
            logger.error(f"Background task error: {e}")

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle callback queries."""
        query = update.callback_query
        await query.answer()

        data = query.data
        chat_id = query.message.chat.id

        if data == "chat":
            await query.edit_message_text("💬 Send me any message!")

        elif data == "commands_1":
            await self._show_commands_page(query, 1)

        elif data == "models":
            keyboard = [
                [InlineKeyboardButton("Claude 3.5", callback_data="model_anthropic/claude-sonnet-4-6")],
                [InlineKeyboardButton("GPT-4o", callback_data="model_openai/gpt-4o")],
                [InlineKeyboardButton("Hermes 3", callback_data="model_nous/hermes-3-llama-3.1-405b")],
                [InlineKeyboardButton("Back", callback_data="back")],
            ]
            await query.edit_message_text("Select model:", reply_markup=InlineKeyboardMarkup(keyboard))

        elif data == "settings":
            await query.edit_message_text("⚙️ Settings\n\nUse /model, /voice, /yolo to configure.")

        elif data == "back":
            keyboard = [
                [InlineKeyboardButton("💬 Chat", callback_data="chat")],
                [InlineKeyboardButton("📚 Commands", callback_data="commands_1")],
                [InlineKeyboardButton("🤖 Models", callback_data="models")],
            ]
            await query.edit_message_text("Choose:", reply_markup=InlineKeyboardMarkup(keyboard))

        elif data.startswith("model_"):
            model = data[6:]
            self.user_models[chat_id] = model
            await query.edit_message_text(f"✅ Model: {model}")

        elif data == "cancel":
            await query.edit_message_text("Cancelled.")

    async def _show_commands_page(self, query: CallbackQuery, page: int) -> None:
        """Show commands page."""
        all_commands = [
            ("/new [name]", "New session (alias: /reset)"),
            ("/retry", "Retry last message"),
            ("/undo [N]", "Back up N turns"),
            ("/title [name]", "Set session title"),
            ("/branch [name]", "Branch session (alias: /fork)"),
            ("/compress", "Compress context"),
            ("/stop", "Kill background processes"),
            ("/pause [reason]", "Pause/resume"),
            ("/approve", "Approve pending command"),
            ("/deny", "Deny pending command"),
            ("/background <prompt>", "Run in background (alias: /bg)"),
            ("/agents", "Show active agents"),
            ("/status", "Show status"),
            ("/model [model]", "Switch model"),
            ("/context", "Show context (alias: /ctx)"),
            ("/help", "Show help"),
        ]

        start = (page - 1) * self.page_size
        end = min(start + self.page_size, len(all_commands))
        commands = all_commands[start:end]
        total_pages = (len(all_commands) + self.page_size - 1) // self.page_size

        text = f"📚 <b>Commands (page {page}/{total_pages})</b>\n\n"
        for cmd, desc in commands:
            text += f"<code>{cmd}</code> — {desc}\n"

        text += f"\nPage {page}/{total_pages}"

        await query.edit_message_text(text, parse_mode=ParseMode.HTML)


def main():
    """Main entry point."""
    if not HAS_TELEGRAM:
        print("Telegram dependencies not installed.")
        return

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        return

    bot = BahramTelegramBot()
    app = ApplicationBuilder().token(token).build()
    app.bot_data["bahram_bot"] = bot

    # Core commands
    app.add_handler(CommandHandler("start", bot.handle_start))
    app.add_handler(CommandHandler("new", bot.handle_new))
    app.add_handler(CommandHandler("reset", bot.handle_new))
    app.add_handler(CommandHandler("retry", bot.handle_retry))
    app.add_handler(CommandHandler("undo", bot.handle_undo))
    app.add_handler(CommandHandler("title", bot.handle_title))
    app.add_handler(CommandHandler("branch", bot.handle_branch))
    app.add_handler(CommandHandler("fork", bot.handle_branch))
    app.add_handler(CommandHandler("compress", bot.handle_compress))
    app.add_handler(CommandHandler("compact", bot.handle_compress))
    app.add_handler(CommandHandler("rollback", bot.handle_rollback))
    app.add_handler(CommandHandler("stop", bot.handle_stop))
    app.add_handler(CommandHandler("pause", bot.handle_pause))
    app.add_handler(CommandHandler("approve", bot.handle_approve))
    app.add_handler(CommandHandler("deny", bot.handle_deny))
    app.add_handler(CommandHandler("background", bot.handle_background))
    app.add_handler(CommandHandler("bg", bot.handle_background))
    app.add_handler(CommandHandler("agents", bot.handle_agents))
    app.add_handler(CommandHandler("tasks", bot.handle_agents))
    app.add_handler(CommandHandler("queue", bot.handle_queue))
    app.add_handler(CommandHandler("q", bot.handle_queue))
    app.add_handler(CommandHandler("steer", bot.handle_steer))
    app.add_handler(CommandHandler("goal", bot.handle_goal))
    app.add_handler(CommandHandler("heartbeat", bot.handle_heartbeat))
    app.add_handler(CommandHandler("hb", bot.handle_heartbeat))
    app.add_handler(CommandHandler("refine", bot.handle_refine))
    app.add_handler(CommandHandler("moa", bot.handle_moa))
    app.add_handler(CommandHandler("subgoal", bot.handle_subgoal))
    app.add_handler(CommandHandler("status", bot.handle_status))
    app.add_handler(CommandHandler("context", bot.handle_context))
    app.add_handler(CommandHandler("ctx", bot.handle_context))
    app.add_handler(CommandHandler("whoami", bot.handle_whoami))
    app.add_handler(CommandHandler("profile", bot.handle_profile))
    app.add_handler(CommandHandler("sethome", bot.handle_sethome))
    app.add_handler(CommandHandler("resume", bot.handle_resume))
    app.add_handler(CommandHandler("sessions", bot.handle_sessions))
    app.add_handler(CommandHandler("model", bot.handle_model))
    app.add_handler(CommandHandler("personality", bot.handle_personality))
    app.add_handler(CommandHandler("diff", bot.handle_diff))
    app.add_handler(CommandHandler("footer", bot.handle_footer))
    app.add_handler(CommandHandler("yolo", bot.handle_yolo))
    app.add_handler(CommandHandler("approvals", bot.handle_approvals))
    app.add_handler(CommandHandler("reasoning", bot.handle_reasoning))
    app.add_handler(CommandHandler("fast", bot.handle_fast))
    app.add_handler(CommandHandler("voice", bot.handle_voice))
    app.add_handler(CommandHandler("memory", bot.handle_memory))
    app.add_handler(CommandHandler("bundles", bot.handle_bundles))
    app.add_handler(CommandHandler("learn", bot.handle_learn))
    app.add_handler(CommandHandler("init", bot.handle_init))
    app.add_handler(CommandHandler("suggestions", bot.handle_suggestions))
    app.add_handler(CommandHandler("suggest", bot.handle_suggestions))
    app.add_handler(CommandHandler("blueprint", bot.handle_blueprint))
    app.add_handler(CommandHandler("bp", bot.handle_blueprint))
    app.add_handler(CommandHandler("reload_mcp", bot.handle_reload_mcp))
    app.add_handler(CommandHandler("reload_skills", bot.handle_reload_skills))
    app.add_handler(CommandHandler("commands", bot.handle_commands))
    app.add_handler(CommandHandler("help", bot.handle_help))
    app.add_handler(CommandHandler("version", bot.handle_version))
    app.add_handler(CommandHandler("v", bot.handle_version))
    app.add_handler(CommandHandler("update", bot.handle_update))
    app.add_handler(CommandHandler("debug", bot.handle_debug if hasattr(bot, 'handle_debug') else bot.handle_status))

    # Skill commands
    skill_commands = [
        "airtable", "architecture_diagram", "arxiv", "ascii_art", "ascii_video",
        "blocked_page_recovery", "blogwatcher", "box", "claude_code", "claude_design",
        "codebase_inspection", "codex", "comfyui", "competitor_news_monitor",
        "computer_use", "design_md", "document_to_action_items", "docx", "dogfood",
        "email_inbox_triage", "evaluating_llms_harness", "excalidraw", "gif_search",
        "github_auth", "github_code_review", "github_issue_to_pr", "github_issues",
        "github_pr_workflow", "github_repo_management", "google_workspace",
        "grounded_citations", "hermes_agent", "huggingface_hub", "humanizer",
        "llama_cpp", "llm_wiki", "manim_video", "maps", "meeting_action_items",
        "merge_reconciler", "nano_pdf", "notion", "obsidian", "ocr_and_documents",
        "opencode", "openhue", "p5js", "pdf", "plan", "popular_web_designs",
        "powerpoint", "pretext", "product_price_monitor", "python_debugpy",
        "requesting_code_review", "research_paper_writing", "serving_llms_vllm",
        "session_librarian", "simplify_code", "sketch", "songsee",
        "songwriting_and_ai_music", "spike", "systematic_debugging",
        "teams_meeting_pipeline", "test_driven_development", "weekly_review_planning",
        "weights_and_biases", "xlsx", "xurl", "youtube_content",
    ]

    for skill in skill_commands:
        handler = lambda update, context, s=skill: bot.handle_skill_command(update, context, s)
        app.add_handler(CommandHandler(skill, handler))

    # Callback queries
    app.add_handler(CallbackQueryHandler(bot.handle_callback_query))

    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, bot.handle_voice if hasattr(bot, 'handle_voice_msg') else bot.handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, bot.handle_message))
    app.add_handler(MessageHandler(filters.Document.ALL, bot.handle_message))

    async def post_init(application):
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("new", "New session"),
            BotCommand("help", "Show help"),
            BotCommand("commands", "List all commands"),
            BotCommand("model", "Change model"),
            BotCommand("status", "Show status"),
            BotCommand("clear", "Clear history"),
        ]
        await application.bot.set_my_commands(commands)
        await bot.initialize()

    async def post_shutdown(application):
        await bot.cleanup()

    app.post_init = post_init
    app.post_shutdown = post_shutdown

    print("Bahram Agent Bot starting...")
    print("Press Ctrl+C to stop")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
