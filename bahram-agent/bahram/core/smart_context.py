"""
Smart context.

Public objects: ``ContextWindow``, ``SmartContextManager``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ContextWindow:
    """
    Context window.

    Attributes:
        content (str): text content to process.
        tokens (int): numeric value for tokens.
        priority (int): numeric value for priority.
        metadata (dict): mapping of metadata.
    """

    content: str
    tokens: int
    priority: int = 0
    metadata: dict = field(default_factory=dict)


class SmartContextManager:
    """
    Smart context manager.
    """

    def __init__(self, max_tokens: int = 8192) -> None:
        """
        Initialise a SmartContextManager instance.

        Args:
            max_tokens (int): numeric value for max tokens. Defaults to ``8192``.
        """
        self.max_tokens = max_tokens
        self._windows: list[ContextWindow] = []
        self._system_prompt: str = ""
        self._history: list[dict] = []

    def set_system_prompt(self, prompt: str) -> None:
        """
        Set the system prompt.

        Args:
            prompt (str): prompt string.
        """
        self._system_prompt = prompt

    def add_context(
        self,
        content: str,
        priority: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Add context.

        Args:
            content (str): text content to process.
            priority (int): numeric value for priority. Defaults to ``0``.
            metadata (dict): mapping of metadata. Defaults to ``None``.
        """
        tokens = self._estimate_tokens(content)
        self._windows.append(
            ContextWindow(
                content=content,
                tokens=tokens,
                priority=priority,
                metadata=metadata or {},
            )
        )

    def add_history(self, role: str, content: str) -> None:
        """
        Add history.

        Args:
            role (str): role string.
            content (str): text content to process.
        """
        self._history.append({"role": role, "content": content})

    def build_context(self) -> list[dict]:
        """
        Build context.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        messages = []

        if self._system_prompt:
            messages.append({"role": "system", "content": self._system_prompt})
            used_tokens = self._estimate_tokens(self._system_prompt)
        else:
            used_tokens = 0

        sorted_windows = sorted(self._windows, key=lambda w: w.priority, reverse=True)
        for window in sorted_windows:
            if used_tokens + window.tokens <= self.max_tokens * 0.7:
                messages.append({"role": "system", "content": window.content})
                used_tokens += window.tokens

        for msg in reversed(self._history):
            msg_tokens = self._estimate_tokens(msg["content"])
            if used_tokens + msg_tokens <= self.max_tokens * 0.9:
                messages.insert(-1, msg)
                used_tokens += msg_tokens

        return messages

    def _estimate_tokens(self, text: str) -> int:

        return len(text) // 4

    def get_usage(self) -> dict[str, int]:
        """
        Return the usage.

        Returns:
            dict[str, int]: a mapping of str, int.
        """
        total_tokens = sum(w.tokens for w in self._windows)
        history_tokens = sum(self._estimate_tokens(m["content"]) for m in self._history)
        return {
            "max_tokens": self.max_tokens,
            "context_tokens": total_tokens,
            "history_tokens": history_tokens,
            "total_used": total_tokens + history_tokens,
            "remaining": self.max_tokens - total_tokens - history_tokens,
        }

    def optimize(self) -> int:
        """
        Optimize.

        Returns:
            int: the computed numeric value.
        """
        usage = self.get_usage()
        if usage["remaining"] > 0:
            return 0

        removed = 0
        self._windows.sort(key=lambda w: w.priority)
        while self._windows and usage["remaining"] < 0:
            removed_window = self._windows.pop(0)
            usage["remaining"] += removed_window.tokens
            removed += 1

        return removed

    def clear(self) -> None:
        """
        Clear.
        """
        self._windows.clear()
        self._history.clear()

    def format_context(self) -> str:
        """
        Format context.

        Returns:
            str: the rendered string.
        """
        usage = self.get_usage()
        lines = [
            "## Context Window",
            f"Max: {usage['max_tokens']} tokens",
            f"Used: {usage['total_used']} tokens",
            f"Remaining: {usage['remaining']} tokens",
            f"Context windows: {len(self._windows)}",
            f"History messages: {len(self._history)}",
        ]
        return "\n".join(lines)

    def build_messages(self) -> list[Any]:
        """
        Build messages.

        Returns:
            list[Any]: a sequence of Any entries (empty when there is nothing to report).
        """
        from bahram.core.engine import Message, MessageRole

        messages = []
        used_tokens = 0

        if self._system_prompt:
            messages.append(Message(role=MessageRole.SYSTEM, content=self._system_prompt))
            used_tokens += self._estimate_tokens(self._system_prompt)

        sorted_windows = sorted(self._windows, key=lambda w: w.priority, reverse=True)
        for window in sorted_windows:
            if used_tokens + window.tokens <= self.max_tokens * 0.7:
                messages.append(Message(role=MessageRole.SYSTEM, content=window.content))
                used_tokens += window.tokens

        for msg in reversed(self._history):
            msg_tokens = self._estimate_tokens(msg["content"])
            if used_tokens + msg_tokens <= self.max_tokens * 0.9:
                role = MessageRole.USER if msg["role"] == "user" else MessageRole.ASSISTANT
                messages.append(Message(role=role, content=msg["content"]))
                used_tokens += msg_tokens

        return messages
