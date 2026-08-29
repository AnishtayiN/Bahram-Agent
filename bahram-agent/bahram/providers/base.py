"""Base LLM provider."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from bahram.core.engine import AgentResponse, Message


class BaseProvider(ABC):
    """Base class for LLM providers."""

    def __init__(self, config: Any) -> None:
        self.config = config

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AgentResponse:
        """Generate a completion."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion."""
        ...
