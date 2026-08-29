from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional

@dataclass
class PlatformMessage:
    ""

    platform: str
    user_id: str
    user_name: str
    content: str
    chat_id: str
    message_id: str
    timestamp: float
    reply_to: Optional[str] = None

class BasePlatform(ABC):
    ""

    def __init__(self, config: Any) -> None:
        self.config = config
        self._message_handler: Optional[Callable] = None

    @property
    @abstractmethod
    def name(self) -> str:
        ""
        ...

    @abstractmethod
    async def start(self) -> None:
        ""
        ...

    @abstractmethod
    async def stop(self) -> None:
        ""
        ...

    @abstractmethod
    async def send_message(self, chat_id: str, content: str) -> None:
        ""
        ...

    @abstractmethod
    async def reply(self, message: PlatformMessage, content: str) -> None:
        ""
        ...

    def set_message_handler(self, handler: Callable) -> None:
        ""
        self._message_handler = handler

    async def _handle_message(self, message: PlatformMessage) -> None:
        ""
        if self._message_handler:
            await self._message_handler(message)
