"""Background review and self-improvement for Bahram Agent."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class ReviewResult:
    """Result from a background review."""

    memory_updates: list[dict] = field(default_factory=list)
    skill_updates: list[dict] = field(default_factory=list)
    summary: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class BackgroundReviewer:
    """Auto-review conversations for learning."""

    def __init__(self) -> None:
        self._enabled = True
        self._review_fn: Optional[Callable] = None

    def set_review_function(self, fn: Callable) -> None:
        """Set the review function."""
        self._review_fn = fn

    async def review_conversation(
        self,
        messages: list[dict],
        current_memory: dict = None,
    ) -> ReviewResult:
        """Review a conversation and extract learnings."""
        result = ReviewResult()

        if not self._enabled or not self._review_fn:
            return result

        try:
            review_output = await self._review_fn(messages, current_memory)
            if review_output:
                result.memory_updates = review_output.get("memory_updates", [])
                result.skill_updates = review_output.get("skill_updates", [])
                result.summary = review_output.get("summary", "")
        except Exception as e:
            logger.error(f"Background review failed: {e}")

        return result

    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable background review."""
        self._enabled = enabled

    def is_enabled(self) -> bool:
        """Check if enabled."""
        return self._enabled
