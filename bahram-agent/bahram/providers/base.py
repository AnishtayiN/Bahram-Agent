from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from bahram.core.engine import AgentResponse, Message

class BaseProvider(ABC):
    ""

    def __init__(self, config: Any) -> None:
        self.config = config

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AgentResponse:
        ""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        ""
        ...
