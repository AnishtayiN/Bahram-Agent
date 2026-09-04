"""
Context.

Public objects: ``ContextWindow``, ``Context``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from bahram.core.engine import Message, MessageRole

logger = logging.getLogger(__name__)


@dataclass
class ContextWindow:
    """
    Context window.

    Attributes:
        max_turns (int): numeric value for max turns.
        max_tokens (int): numeric value for max tokens.
        messages (list[Message]): chat messages to send to the model.
        summaries (list[str]): collection of summaries.
    """

    max_turns: int = 20
    max_tokens: int = 8000
    messages: list[Message] = field(default_factory=list)
    summaries: list[str] = field(default_factory=list)

    def add_message(self, message: Message) -> None:
        """
        Add message.

        Args:
            message (Message): message to process.
        """
        self.messages.append(message)
        self._trim_if_needed()

    def add_messages(self, messages: list[Message]) -> None:
        """
        Add messages.

        Args:
            messages (list[Message]): chat messages to send to the model.
        """
        self.messages.extend(messages)
        self._trim_if_needed()

    def get_messages(self) -> list[Message]:
        """
        Return the messages.

        Returns:
            list[Message]: a sequence of Message entries (empty when there is nothing to report).
        """
        return self.messages.copy()

    def get_system_prompt(self) -> str | None:
        """
        Return the system prompt.

        Returns:
            str | None: the resulting object, or ``None`` when it is not available.
        """
        for msg in self.messages:
            if msg.role == MessageRole.SYSTEM:
                return msg.content
        return None

    def set_system_prompt(self, prompt: str) -> None:
        """
        Set the system prompt.

        Args:
            prompt (str): prompt string.
        """
        for i, msg in enumerate(self.messages):
            if msg.role == MessageRole.SYSTEM:
                self.messages[i] = Message(role=MessageRole.SYSTEM, content=prompt)
                return
        self.messages.insert(0, Message(role=MessageRole.SYSTEM, content=prompt))

    def clear(self) -> None:
        """
        Clear.
        """
        self.messages.clear()
        self.summaries.clear()

    def _trim_if_needed(self) -> None:

        system_msgs = [m for m in self.messages if m.role == MessageRole.SYSTEM]
        other_msgs = [m for m in self.messages if m.role != MessageRole.SYSTEM]

        turn_count = sum(
            1 for m in other_msgs if m.role in (MessageRole.USER, MessageRole.ASSISTANT)
        )

        if turn_count > self.max_turns:
            msgs_to_summarize = other_msgs[: len(other_msgs) // 2]
            summary = self._summarize_messages(msgs_to_summarize)
            self.summaries.append(summary)

            other_msgs = other_msgs[len(msgs_to_summarize) :]

            logger.debug(f"Trimmed context: summarized {len(msgs_to_summarize)} messages")

        self.messages = system_msgs + other_msgs

    def _summarize_messages(self, messages: list[Message]) -> str:

        user_msgs = [m for m in messages if m.role == MessageRole.USER]
        if user_msgs:
            last_user_msg = user_msgs[-1].content[:100]
            return f"[Summary of conversation up to: {last_user_msg}...]"
        return "[Empty conversation summary]"

    def to_dict(self) -> dict[str, Any]:
        """
        Serialise the object to a JSON-serialisable dictionary.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {
            "messages": [
                {
                    "role": m.role.value,
                    "content": m.content,
                    "name": m.name,
                    "timestamp": m.timestamp,
                }
                for m in self.messages
            ],
            "summaries": self.summaries,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextWindow:
        """
        Build an instance from dict.

        Args:
            data (dict[str, Any]): mapping of data.

        Returns:
            ContextWindow: the resulting ContextWindow.
        """
        messages = [
            Message(
                role=MessageRole(m["role"]),
                content=m["content"],
                name=m.get("name"),
                timestamp=m.get("timestamp", time.time()),
            )
            for m in data.get("messages", [])
        ]
        return cls(
            messages=messages,
            summaries=data.get("summaries", []),
        )


class Context:
    """
    Context.
    """

    def __init__(self, max_turns: int = 20) -> None:
        """
        Initialise a Context instance.

        Args:
            max_turns (int): numeric value for max turns. Defaults to ``20``.
        """
        self.max_turns = max_turns
        self._contexts: dict[str, ContextWindow] = {}
        self._active: str | None = None

    def create(self, session_id: str) -> ContextWindow:
        """
        Create.

        Args:
            session_id (str): session identifier.

        Returns:
            ContextWindow: the resulting ContextWindow.
        """
        ctx = ContextWindow(max_turns=self.max_turns)
        self._contexts[session_id] = ctx
        return ctx

    def get(self, session_id: str) -> ContextWindow | None:
        """
        Get.

        Args:
            session_id (str): session identifier.

        Returns:
            ContextWindow | None: the resulting object, or ``None`` when it is not available.
        """
        return self._contexts.get(session_id)

    def get_or_create(self, session_id: str) -> ContextWindow:
        """
        Return the or create.

        Args:
            session_id (str): session identifier.

        Returns:
            ContextWindow: the resulting ContextWindow.
        """
        if session_id not in self._contexts:
            self.create(session_id)
        return self._contexts[session_id]

    def delete(self, session_id: str) -> None:
        """
        Delete.

        Args:
            session_id (str): session identifier.
        """
        self._contexts.pop(session_id, None)

    def set_active(self, session_id: str) -> None:
        """
        Set the active.

        Args:
            session_id (str): session identifier.
        """
        self._active = session_id

    def get_active(self) -> ContextWindow | None:
        """
        Return the active.

        Returns:
            ContextWindow | None: the resulting object, or ``None`` when it is not available.
        """
        if self._active:
            return self._contexts.get(self._active)
        return None

    def list_sessions(self) -> list[str]:
        """
        List sessions.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        return list(self._contexts.keys())

    def clear(self, session_id: str) -> None:
        """
        Clear.

        Args:
            session_id (str): session identifier.
        """
        if session_id in self._contexts:
            self._contexts[session_id].clear()
