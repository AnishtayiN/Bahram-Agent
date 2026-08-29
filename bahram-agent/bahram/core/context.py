"""Context management for conversations."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from bahram.core.engine import Message, MessageRole

logger = logging.getLogger(__name__)


@dataclass
class ContextWindow:
    """Manages the context window for a conversation."""

    max_turns: int = 20
    max_tokens: int = 8000
    messages: list[Message] = field(default_factory=list)
    summaries: list[str] = field(default_factory=list)

    def add_message(self, message: Message) -> None:
        """Add a message to the context."""
        self.messages.append(message)
        self._trim_if_needed()

    def add_messages(self, messages: list[Message]) -> None:
        """Add multiple messages to the context."""
        self.messages.extend(messages)
        self._trim_if_needed()

    def get_messages(self) -> list[Message]:
        """Get all messages in the context."""
        return self.messages.copy()

    def get_system_prompt(self) -> Optional[str]:
        """Get the system prompt if present."""
        for msg in self.messages:
            if msg.role == MessageRole.SYSTEM:
                return msg.content
        return None

    def set_system_prompt(self, prompt: str) -> None:
        """Set or update the system prompt."""
        for i, msg in enumerate(self.messages):
            if msg.role == MessageRole.SYSTEM:
                self.messages[i] = Message(role=MessageRole.SYSTEM, content=prompt)
                return
        self.messages.insert(0, Message(role=MessageRole.SYSTEM, content=prompt))

    def clear(self) -> None:
        """Clear all messages."""
        self.messages.clear()
        self.summaries.clear()

    def _trim_if_needed(self) -> None:
        """Trim context if it exceeds limits."""
        # Keep system prompt
        system_msgs = [m for m in self.messages if m.role == MessageRole.SYSTEM]
        other_msgs = [m for m in self.messages if m.role != MessageRole.SYSTEM]

        # Count user/assistant turns (excluding tool messages)
        turn_count = sum(
            1
            for m in other_msgs
            if m.role in (MessageRole.USER, MessageRole.ASSISTANT)
        )

        if turn_count > self.max_turns:
            # Summarize older messages
            msgs_to_summarize = other_msgs[: len(other_msgs) // 2]
            summary = self._summarize_messages(msgs_to_summarize)
            self.summaries.append(summary)

            # Keep only recent messages
            other_msgs = other_msgs[len(msgs_to_summarize) :]

            logger.debug(
                f"Trimmed context: summarized {len(msgs_to_summarize)} messages"
            )

        self.messages = system_msgs + other_msgs

    def _summarize_messages(self, messages: list[Message]) -> str:
        """Create a summary of messages."""
        # Simple summary - in production, use LLM
        user_msgs = [m for m in messages if m.role == MessageRole.USER]
        if user_msgs:
            last_user_msg = user_msgs[-1].content[:100]
            return f"[Summary of conversation up to: {last_user_msg}...]"
        return "[Empty conversation summary]"

    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary."""
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
        """Create context from dictionary."""
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
    """Manages multiple conversation contexts."""

    def __init__(self, max_turns: int = 20) -> None:
        self.max_turns = max_turns
        self._contexts: dict[str, ContextWindow] = {}
        self._active: Optional[str] = None

    def create(self, session_id: str) -> ContextWindow:
        """Create a new context window."""
        ctx = ContextWindow(max_turns=self.max_turns)
        self._contexts[session_id] = ctx
        return ctx

    def get(self, session_id: str) -> Optional[ContextWindow]:
        """Get a context window by session ID."""
        return self._contexts.get(session_id)

    def get_or_create(self, session_id: str) -> ContextWindow:
        """Get or create a context window."""
        if session_id not in self._contexts:
            self.create(session_id)
        return self._contexts[session_id]

    def delete(self, session_id: str) -> None:
        """Delete a context window."""
        self._contexts.pop(session_id, None)

    def set_active(self, session_id: str) -> None:
        """Set the active context."""
        self._active = session_id

    def get_active(self) -> Optional[ContextWindow]:
        """Get the active context."""
        if self._active:
            return self._contexts.get(self._active)
        return None

    def list_sessions(self) -> list[str]:
        """List all session IDs."""
        return list(self._contexts.keys())

    def clear(self, session_id: str) -> None:
        """Clear a context."""
        if session_id in self._contexts:
            self._contexts[session_id].clear()
