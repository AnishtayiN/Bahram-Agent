from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


class ContextCategory(str):
    STABLE = "stable"
    CONTEXTUAL = "contextual"
    VOLATILE = "volatile"


@dataclass
class ContextElement:
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
    def __init__(self, max_tokens: int = 8192) -> None:
        self.max_tokens = max_tokens
        self._stable: list[ContextElement] = []
        self._contextual: list[ContextElement] = []
        self._volatile: list[ContextElement] = []
        self._trace: list[dict[str, Any]] = []

    def set_stable(self, elements: list[ContextElement]) -> None:
        self._stable = elements

    def add_stable(self, content: str, source: str, **kwargs: Any) -> None:
        self._stable.append(ContextElement(
            content=content, category=ContextCategory.STABLE, source=source, **kwargs,
        ))

    def add_contextual(self, content: str, source: str, **kwargs: Any) -> None:
        self._contextual.append(ContextElement(
            content=content, category=ContextCategory.CONTEXTUAL, source=source, **kwargs,
        ))

    def add_volatile(self, content: str, source: str, **kwargs: Any) -> None:
        self._volatile.append(ContextElement(
            content=content, category=ContextCategory.VOLATILE, source=source, **kwargs,
        ))

    def build_messages(self) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        remaining = self.max_tokens
        for element in self._stable:
            if element.tokens <= remaining:
                messages.append({"role": "system", "content": element.content})
                remaining -= element.tokens
                self._trace.append({"source": element.source, "category": "stable", "included": True})
        for element in sorted(self._contextual, key=lambda e: e.priority, reverse=True):
            if element.tokens <= remaining:
                messages.append({"role": "system", "content": element.content})
                remaining -= element.tokens
                self._trace.append({"source": element.source, "category": "contextual", "included": True})
        for element in sorted(self._volatile, key=lambda e: e.priority, reverse=True):
            if element.tokens <= remaining:
                messages.append({"role": "system", "content": element.content})
                remaining -= element.tokens
                self._trace.append({"source": element.source, "category": "volatile", "included": True})
        return messages

    def get_usage(self) -> dict[str, int]:
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
        return list(self._trace)

    def clear_volatile(self) -> int:
        count = len(self._volatile)
        self._volatile.clear()
        return count

    def optimize(self) -> int:
        usage = self.get_usage()
        if usage["remaining"] >= 0:
            return 0
        removed = 0
        self._volatile.sort(key=lambda e: e.priority)
        while self._volatile and usage["remaining"] < 0:
            element = self._volatile.pop(0)
            usage["remaining"] += element.tokens
            removed += 1
            self._trace.append({"source": element.source, "category": "volatile", "included": False, "reason": "optimized"})
        return removed
