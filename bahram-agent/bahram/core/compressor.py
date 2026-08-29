"""Context compression for Bahram Agent."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class CompressionResult:
    """Result of context compression."""

    compressed: str
    original_tokens: int
    compressed_tokens: int
    ratio: float


class ContextCompressor:
    """Compress context to reduce token usage."""

    def __init__(self) -> None:
        self._compression_level = 0.5  # 0-1, higher = more compression
        self._enabled = True

    async def compress(
        self,
        messages: list[dict],
        model_fn: Callable = None,
        target_tokens: int = 4000,
    ) -> CompressionResult:
        """Compress conversation context."""
        if not self._enabled or not messages:
            return CompressionResult(
                compressed=json.dumps(messages),
                original_tokens=0,
                compressed_tokens=0,
                ratio=1.0,
            )

        # Estimate original tokens
        original_text = json.dumps(messages)
        original_tokens = len(original_text) // 4  # Rough estimate

        if original_tokens <= target_tokens:
            return CompressionResult(
                compressed=original_text,
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                ratio=1.0,
            )

        # Use model-based compression if available
        if model_fn:
            compressed = await self._model_compress(messages, model_fn, target_tokens)
        else:
            compressed = self._heuristic_compress(messages, target_tokens)

        compressed_tokens = len(compressed) // 4
        ratio = compressed_tokens / original_tokens if original_tokens > 0 else 1.0

        return CompressionResult(
            compressed=compressed,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            ratio=ratio,
        )

    async def _model_compress(
        self,
        messages: list[dict],
        model_fn: Callable,
        target_tokens: int,
    ) -> str:
        """Use LLM to compress context."""
        full_context = json.dumps(messages)
        prompt = f"""Compress this conversation context to approximately {target_tokens} tokens.
Keep the most important information, key decisions, and recent context.
Remove redundant, repetitive, or less important parts.

Context:
{full_context[:8000]}

Return the compressed context as JSON:"""

        try:
            response = await model_fn([{"role": "user", "content": prompt}])
            return response
        except Exception as e:
            logger.warning(f"Model compression failed: {e}")
            return self._heuristic_compress(messages, target_tokens)

    def _heuristic_compress(self, messages: list[dict], target_tokens: int) -> str:
        """Heuristic compression."""
        if not messages:
            return "[]"

        # Keep system message
        result = []
        if messages[0].get("role") == "system":
            result.append(messages[0])
            messages = messages[1:]

        # Keep last N messages
        target_count = min(len(messages), target_tokens // 200)
        if target_count < len(messages):
            result.extend(messages[-target_count:])
        else:
            result.extend(messages)

        # Add compression marker
        if len(messages) > target_count:
            skipped = len(messages) - target_count
            result.insert(1, {
                "role": "system",
                "content": f"[Context compressed: {skipped} earlier messages summarized]",
            })

        return json.dumps(result)

    def set_level(self, level: float) -> None:
        """Set compression level (0-1)."""
        self._compression_level = max(0, min(1, level))

    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable compression."""
        self._enabled = enabled
