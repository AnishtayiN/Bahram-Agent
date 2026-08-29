"""Fallback providers for Bahram Agent."""

from __future__ import annotations

import logging
from typing import Any, Optional

from bahram.providers.base import BaseProvider
from bahram.core.engine import AgentResponse, Message

logger = logging.getLogger(__name__)


class FallbackProvider(BaseProvider):
    """Provider with automatic failover to backup providers."""

    def __init__(self, primary: BaseProvider, fallbacks: list[BaseProvider] = None) -> None:
        self.primary = primary
        self.fallbacks = fallbacks or []
        self._current = primary

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AgentResponse:
        """Generate a completion with fallback."""
        # Try primary first
        try:
            return await self.primary.complete(messages, tools, **kwargs)
        except Exception as e:
            logger.warning(f"Primary provider failed: {e}")

        # Try fallbacks
        for fallback in self.fallbacks:
            try:
                logger.info(f"Trying fallback provider: {fallback.__class__.__name__}")
                result = await fallback.complete(messages, tools, **kwargs)
                self._current = fallback
                return result
            except Exception as e:
                logger.warning(f"Fallback provider failed: {e}")

        raise Exception("All providers failed")

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ):
        """Stream a completion with fallback."""
        # Try primary first
        try:
            async for chunk in self.primary.stream(messages, tools, **kwargs):
                yield chunk
            return
        except Exception as e:
            logger.warning(f"Primary provider stream failed: {e}")

        # Try fallbacks
        for fallback in self.fallbacks:
            try:
                logger.info(f"Trying fallback provider stream: {fallback.__class__.__name__}")
                async for chunk in fallback.stream(messages, tools, **kwargs):
                    yield chunk
                self._current = fallback
                return
            except Exception as e:
                logger.warning(f"Fallback provider stream failed: {e}")

        raise Exception("All providers failed")

    def get_current_provider(self) -> str:
        """Get the name of the current active provider."""
        return self._current.__class__.__name__

    def add_fallback(self, provider: BaseProvider) -> None:
        """Add a fallback provider."""
        self.fallbacks.append(provider)

    def remove_fallback(self, provider: BaseProvider) -> None:
        """Remove a fallback provider."""
        self.fallbacks = [p for p in self.fallbacks if p is not provider]
