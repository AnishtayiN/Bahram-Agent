"""
Context architecture.

Public objects: ``ContextCategory``, ``ContextElement``, ``ContextArchitecture``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class ContextCategory(str):
    """
    Context category.
    """

    STABLE = "stable"
    CONTEXTUAL = "contextual"
    VOLATILE = "volatile"


@dataclass
class ContextElement:
    """
    Context element.

    Attributes:
        content (str): text content to process.
        category (str): category string.
        source (str): source string.
        scope (str): scope string.
        priority (int): numeric value for priority.
        timestamp (float): numeric value for timestamp.
        relevance (float): numeric value for relevance.
        tokens (int): numeric value for tokens.
        metadata (dict[str, Any]): mapping of metadata.
    """

    content: str
    category: str
    source: str
    scope: str = "global"
    priority: int = 0
    timestamp: float = field(default_factory=time.time)
    relevance: float = 1.0
    tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.tokens == 0:
            self.tokens = len(self.content) // 4


class ContextArchitecture:
    """
    Context architecture.
    """

    def __init__(self, max_tokens: int = 8192) -> None:
        """
        Initialise a ContextArchitecture instance.

        Args:
            max_tokens (int): numeric value for max tokens. Defaults to ``8192``.
        """
        self.max_tokens = max_tokens
        self._stable: list[ContextElement] = []
        self._contextual: list[ContextElement] = []
        self._volatile: list[ContextElement] = []
        self._trace: list[dict[str, Any]] = []

    def set_stable(self, elements: list[ContextElement]) -> None:
        """
        Set the stable.

        Args:
            elements (list[ContextElement]): collection of elements.
        """
        self._stable = elements

    def add_stable(self, content: str, source: str, **kwargs: Any) -> None:
        """
        Add stable.

        Args:
            content (str): text content to process.
            source (str): source string.
            **kwargs (Any): keyword arguments forwarded to the implementation.
        """
        self._stable.append(
            ContextElement(
                content=content,
                category=ContextCategory.STABLE,
                source=source,
                **kwargs,
            )
        )

    def add_contextual(self, content: str, source: str, **kwargs: Any) -> None:
        """
        Add contextual.

        Args:
            content (str): text content to process.
            source (str): source string.
            **kwargs (Any): keyword arguments forwarded to the implementation.
        """
        self._contextual.append(
            ContextElement(
                content=content,
                category=ContextCategory.CONTEXTUAL,
                source=source,
                **kwargs,
            )
        )

    def add_volatile(self, content: str, source: str, **kwargs: Any) -> None:
        """
        Add volatile.

        Args:
            content (str): text content to process.
            source (str): source string.
            **kwargs (Any): keyword arguments forwarded to the implementation.
        """
        self._volatile.append(
            ContextElement(
                content=content,
                category=ContextCategory.VOLATILE,
                source=source,
                **kwargs,
            )
        )

    def build_messages(self) -> list[dict[str, str]]:
        """
        Build messages.

        Returns:
            list[dict[str, str]]: a sequence of dict[str, str] entries (empty when there is nothing
                to report).
        """
        messages: list[dict[str, str]] = []
        remaining = self.max_tokens
        for element in self._stable:
            if element.tokens <= remaining:
                messages.append({"role": "system", "content": element.content})
                remaining -= element.tokens
                self._trace.append(
                    {"source": element.source, "category": "stable", "included": True}
                )
        for element in sorted(self._contextual, key=lambda e: e.priority, reverse=True):
            if element.tokens <= remaining:
                messages.append({"role": "system", "content": element.content})
                remaining -= element.tokens
                self._trace.append(
                    {"source": element.source, "category": "contextual", "included": True}
                )
        for element in sorted(self._volatile, key=lambda e: e.priority, reverse=True):
            if element.tokens <= remaining:
                messages.append({"role": "system", "content": element.content})
                remaining -= element.tokens
                self._trace.append(
                    {"source": element.source, "category": "volatile", "included": True}
                )
        return messages

    def get_usage(self) -> dict[str, int]:
        """
        Return the usage.

        Returns:
            dict[str, int]: a mapping of str, int.
        """
        stable_tokens = sum(e.tokens for e in self._stable)
        contextual_tokens = sum(e.tokens for e in self._contextual)
        volatile_tokens = sum(e.tokens for e in self._volatile)
        return {
            "max_tokens": self.max_tokens,
            "stable_tokens": stable_tokens,
            "contextual_tokens": contextual_tokens,
            "volatile_tokens": volatile_tokens,
            "total_used": stable_tokens + contextual_tokens + volatile_tokens,
            "remaining": self.max_tokens - stable_tokens - contextual_tokens - volatile_tokens,
        }

    def get_trace(self) -> list[dict[str, Any]]:
        """
        Return the trace.

        Returns:
            list[dict[str, Any]]: a sequence of dict[str, Any] entries (empty when there is nothing
                to report).
        """
        return list(self._trace)

    def clear_volatile(self) -> int:
        """
        Clear volatile.

        Returns:
            int: the computed numeric value.
        """
        count = len(self._volatile)
        self._volatile.clear()
        return count

    def optimize(self) -> int:
        """
        Optimize.

        Returns:
            int: the computed numeric value.
        """
        usage = self.get_usage()
        if usage["remaining"] >= 0:
            return 0
        removed = 0
        self._volatile.sort(key=lambda e: e.priority)
        while self._volatile and usage["remaining"] < 0:
            element = self._volatile.pop(0)
            usage["remaining"] += element.tokens
            removed += 1
            self._trace.append(
                {
                    "source": element.source,
                    "category": "volatile",
                    "included": False,
                    "reason": "optimized",
                }
            )
        return removed
