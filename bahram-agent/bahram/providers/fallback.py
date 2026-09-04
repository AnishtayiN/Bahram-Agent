"""
Fallback.

Public objects: ``FallbackProvider``.
"""

from __future__ import annotations

import logging
from typing import Any

from bahram.core.engine import AgentResponse, Message
from bahram.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class FallbackProvider(BaseProvider):
    """
    Fallback provider.
    """

    def __init__(self, primary: BaseProvider, fallbacks: list[BaseProvider] = None) -> None:
        """
        Initialise a FallbackProvider instance.

        Args:
            primary (BaseProvider): primary.
            fallbacks (list[BaseProvider]): collection of fallbacks. Defaults to ``None``.
        """
        self.primary = primary
        self.fallbacks = fallbacks or []
        self._current = primary

    async def _call_api(
        self,
        messages,
        system_msg=None,
        tools=None,
        model=None,
        temperature=0.7,
        max_tokens=4096,
        **kwargs,
    ):
        raise NotImplementedError("FallbackProvider delegates to child providers via complete()")

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AgentResponse:
        """
        Complete.

        Args:
            messages (list[Message]): chat messages to send to the model.
            tools (list[dict[str, Any]]): collection of tools.
            **kwargs (Any): keyword arguments forwarded to the implementation.

        Returns:
            AgentResponse: the resulting AgentResponse.

        Raises:
            Exception: if the operation cannot be completed.

        Note:
            Coroutine - must be awaited.
        """
        try:
            return await self.primary.complete(messages, tools, **kwargs)
        except Exception as e:
            logger.warning(f"Primary provider failed: {e}")

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
        """
        Stream.

        Args:
            messages (list[Message]): chat messages to send to the model.
            tools (list[dict[str, Any]]): collection of tools.
            **kwargs (Any): keyword arguments forwarded to the implementation.

        Raises:
            Exception: if the operation cannot be completed.

        Note:
            Coroutine - must be awaited.
        """
        try:
            async for chunk in self.primary.stream(messages, tools, **kwargs):
                yield chunk
            return
        except Exception as e:
            logger.warning(f"Primary provider stream failed: {e}")

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
        """
        Return the current provider.

        Returns:
            str: the rendered string.
        """
        return self._current.__class__.__name__

    def add_fallback(self, provider: BaseProvider) -> None:
        """
        Add fallback.

        Args:
            provider (BaseProvider): provider.
        """
        self.fallbacks.append(provider)

    def remove_fallback(self, provider: BaseProvider) -> None:
        """
        Remove fallback.

        Args:
            provider (BaseProvider): provider.
        """
        self.fallbacks = [p for p in self.fallbacks if p is not provider]
