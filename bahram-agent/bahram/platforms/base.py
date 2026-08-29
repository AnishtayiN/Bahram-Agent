"""Base platform class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class PlatformMessage:
    """Message from a platform."""

    platform: str
    user_id: str
    user_name: str
    content: str
    chat_id: str
    message_id: str
    timestamp: float
    reply_to: Optional[str] = None


class BasePlatform(ABC):
    """Base class for platform integrations."""

    def __init__(self, config: Any) -> None:
        self.config = config
        self._message_handler: Optional[Callable] = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Platform name."""
        ...

    @abstractmethod
    async def start(self) -> None:
        """Start the platform."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the platform."""
        ...

    @abstractmethod
    async def send_message(self, chat_id: str, content: str) -> None:
        """Send a message to a chat."""
        ...

    @abstractmethod
    async def reply(self, message: PlatformMessage, content: str) -> None:
        """Reply to a message."""
        ...

    def set_message_handler(self, handler: Callable) -> None:
        """Set the message handler."""
        self._message_handler = handler

    async def _handle_message(self, message: PlatformMessage) -> None:
        """Handle an incoming message."""
        if self._message_handler:
            await self._message_handler(message)
