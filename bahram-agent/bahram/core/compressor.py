"""
Compressor.

Public objects: ``CompressionResult``, ``ContextCompressor``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CompressionResult:
    """
    Compression result.

    Attributes:
        compressed (str): compressed string.
        original_tokens (int): numeric value for original tokens.
        compressed_tokens (int): numeric value for compressed tokens.
        ratio (float): numeric value for ratio.
    """

    compressed: str
    original_tokens: int
    compressed_tokens: int
    ratio: float


class ContextCompressor:
    """
    Context compressor.
    """

    def __init__(self) -> None:
        """
        Initialise a ContextCompressor instance.
        """
        self._compression_level = 0.5
        self._enabled = True

    async def compress(
        self,
        messages: list[dict],
        model_fn: Callable[..., Any] | None = None,
        target_tokens: int = 4000,
    ) -> CompressionResult:
        """
        Compress.

        Args:
            messages (list[dict]): chat messages to send to the model.
            model_fn (Callable): callable used for model fn. Defaults to ``None``.
            target_tokens (int): numeric value for target tokens. Defaults to ``4000``.

        Returns:
            CompressionResult: the resulting CompressionResult.

        Note:
            Coroutine - must be awaited.
        """
        if not self._enabled or not messages:
            return CompressionResult(
                compressed=json.dumps(messages),
                original_tokens=0,
                compressed_tokens=0,
                ratio=1.0,
            )

        original_text = json.dumps(messages)
        original_tokens = len(original_text) // 4

        if original_tokens <= target_tokens:
            return CompressionResult(
                compressed=original_text,
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                ratio=1.0,
            )

        if model_fn is not None:
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
        full_context = json.dumps(messages, default=str)
        msg_count = len(messages)
        prompt = (
            f"Compress the following conversation ({msg_count} messages) into a concise summary. "
            f"Preserve all key information, decisions, tool calls, and results. "
            f"Target approximately {target_tokens} tokens. "
            f"Return ONLY the compressed summary, no preamble.\n\n"
            f"Conversation:\n{full_context[:12000]}"
        )

        try:
            response = await model_fn([{"role": "user", "content": prompt}])
            return response
        except Exception as e:
            logger.warning(f"Model compression failed: {e}")
            return self._heuristic_compress(messages, target_tokens)

    def _heuristic_compress(self, messages: list[dict], target_tokens: int) -> str:
        if not messages:
            return "[]"

        result = []
        if messages[0].get("role") == "system":
            result.append(messages[0])
            messages = messages[1:]

        target_count = min(len(messages), target_tokens // 200)
        if target_count < len(messages):
            result.extend(messages[-target_count:])
        else:
            result.extend(messages)

        if len(messages) > target_count:
            skipped = len(messages) - target_count
            result.insert(
                1,
                {
                    "role": "system",
                    "content": f"[Context compressed: {skipped} earlier messages summarized]",
                },
            )

        return json.dumps(result)

    def set_level(self, level: float) -> None:
        """
        Set the level.

        Args:
            level (float): numeric value for level.
        """
        self._compression_level = max(0, min(1, level))

    def set_enabled(self, enabled: bool) -> None:
        """
        Set the enabled.

        Args:
            enabled (bool): when ``True`` the object is active.
        """
        self._enabled = enabled
