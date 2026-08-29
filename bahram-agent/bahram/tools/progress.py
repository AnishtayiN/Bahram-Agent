"""Tool progress notifications for Bahram Agent."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


class ProgressMode(str, Enum):
    """Progress notification modes."""

    OFF = "off"
    NEW = "new"
    ALL = "all"
    VERBOSE = "verbose"
    LOG = "log"


class ToolProgressNotifier:
    """Notify users about tool execution progress."""

    def __init__(self, mode: ProgressMode = ProgressMode.ALL) -> None:
        self.mode = mode
        self._notify_fn: Optional[Callable] = None
        self._log_file: Optional[str] = None

    def set_notify_function(self, fn: Callable) -> None:
        """Set the notification function."""
        self._notify_fn = fn

    async def notify_start(self, tool: str, args: dict = None) -> None:
        """Notify tool execution started."""
        if self.mode == ProgressMode.OFF:
            return

        icon = self._get_tool_icon(tool)
        message = f"{icon} `{tool}`..."

        if self.mode == ProgressMode.VERBOSE and args:
            args_str = str(args)[:100]
            message += f" {args_str}"

        await self._send(message)

    async def notify_progress(self, tool: str, progress: str) -> None:
        """Notify tool progress."""
        if self.mode not in [ProgressMode.ALL, ProgressMode.VERBOSE]:
            return

        await self._send(f"⏳ {progress}")

    async def notify_complete(self, tool: str, result: Any = None) -> None:
        """Notify tool execution completed."""
        if self.mode == ProgressMode.OFF:
            return

        if self.mode in [ProgressMode.ALL, ProgressMode.VERBOSE]:
            await self._send(f"✅ `{tool}` completed")

    async def notify_error(self, tool: str, error: str) -> None:
        """Notify tool execution error."""
        if self.mode == ProgressMode.OFF:
            return

        await self._send(f"❌ `{tool}` failed: {error[:100]}")

    async def _send(self, message: str) -> None:
        """Send notification."""
        if self._notify_fn:
            try:
                await self._notify_fn(message)
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")

        if self._log_file:
            self._log_to_file(message)

    def _log_to_file(self, message: str) -> None:
        """Log to file."""
        if self._log_file:
            try:
                with open(self._log_file, "a") as f:
                    f.write(f"{message}\n")
            except Exception:
                pass

    def _get_tool_icon(self, tool: str) -> str:
        """Get icon for tool."""
        icons = {
            "terminal": "💻",
            "bash": "💻",
            "read_file": "📄",
            "write_file": "📝",
            "edit": "✏️",
            "patch": "✏️",
            "web_search": "🔍",
            "web_extract": "🌐",
            "browser": "🌐",
            "execute_code": "🐍",
            "memory": "💾",
            "skill": "🛠️",
        }
        return icons.get(tool, "⚙️")
