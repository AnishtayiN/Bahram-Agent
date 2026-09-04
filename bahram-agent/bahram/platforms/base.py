"""
Base.

Public objects: ``PlatformMessage``, ``BasePlatform``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class PlatformMessage:
    """
    Platform message.

    Attributes:
        platform (str): platform string.
        user_id (str): user identifier.
        user_name (str): user name string.
        content (str): text content to process.
        chat_id (str): chat id string.
        message_id (str): message id string.
        timestamp (float): numeric value for timestamp.
        reply_to (str | None): reply to string.
    """

    platform: str
    user_id: str
    user_name: str
    content: str
    chat_id: str
    message_id: str
    timestamp: float
    reply_to: str | None = None


class BasePlatform(ABC):
    """
    Base platform.
    """

    def __init__(self, config: Any) -> None:
        """
        Initialise a BasePlatform instance.

        Args:
            config (Any): configuration object.
        """
        self.config = config
        self._message_handler: Callable | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Platform identifier, e.g. ``telegram``.

        Returns:
            str: short lowercase platform name.
        """
        ...

    @abstractmethod
    async def start(self) -> None:
        """Connect to the platform and begin consuming messages.

        Note:
            Coroutine - must be awaited.
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Disconnect from the platform and release resources.

        Note:
            Coroutine - must be awaited.
        """
        ...

    @abstractmethod
    async def send_message(self, chat_id: str, content: str) -> None:
        """Send a message to a chat.

        Args:
            chat_id (str): platform specific chat identifier.
            content (str): text content to process.

        Note:
            Coroutine - must be awaited.
        """
        ...

    @abstractmethod
    async def reply(self, message: PlatformMessage, content: str) -> None:
        """Reply to an inbound message.

        Args:
            message (PlatformMessage): the inbound message being answered.
            content (str): text content to process.

        Note:
            Coroutine - must be awaited.
        """
        ...

    def set_message_handler(self, handler: Callable) -> None:
        """
        Set the message handler.

        Args:
            handler (Callable): callable used for handler.
        """
        self._message_handler = handler

    async def _handle_message(self, message: PlatformMessage) -> None:
        if self._message_handler:
            await self._message_handler(message)
