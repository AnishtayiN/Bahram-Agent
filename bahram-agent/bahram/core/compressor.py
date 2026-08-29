"""Context compression for Bahram Agent."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CompressionConfig:
    """Compression configuration."""

    enabled: bool = True
    threshold: float = 0.5  # 50% of context window
    target_ratio: float = 0.2  # Keep 20% of threshold
    tail_mode: str = "lean"  # lean or legacy
    protect_last_n: int = 20
    min_tail_user_messages: int = 1
    in_place: bool = True


class ContextCompressor:
    """Context compression system."""

    def __init__(self, config: CompressionConfig = None) -> None:
        self.config = config or CompressionConfig()
        self._previous_summary: Optional[str] = None

    def should_compress(self, token_count: int, max_tokens: int) -> bool:
        """Check if context should be compressed."""
        if not self.config.enabled:
            return False

        usage_ratio = token_count / max_tokens
        return usage_ratio >= self.config.threshold

    def compress(
        self,
        messages: list[dict],
        token_count: int,
        max_tokens: int,
        summary_model: Any = None,
    ) -> tuple[list[dict], str]:
        """Compress messages.

        Returns:
            Tuple of (compressed_messages, summary)
        """
        if not self.should_compress(token_count, max_tokens):
            return messages, ""

        logger.info(f"Compressing context: {token_count} tokens")

        # Calculate how many messages to keep
        total_messages = len(messages)
        keep_count = max(
            self.config.protect_last_n,
            int(total_messages * self.config.target_ratio),
        )

        # Ensure we keep enough user messages
        user_messages = [m for m in messages if m.get("role") == "user"]
        kept_user = [m for m in messages[-keep_count:] if m.get("role") == "user"]

        if len(kept_user) < self.config.min_tail_user_messages:
            # Adjust keep_count to ensure minimum user messages
            keep_count = min(keep_count + self.config.min_tail_user_messages, total_messages)

        # Split messages
        middle = messages[:-keep_count]
        tail = messages[-keep_count:]

        # Generate summary of middle section
        summary = self._generate_summary(middle, summary_model, token_count)

        # Assemble compressed messages
        if self.config.in_place:
            # Keep system message if present
            system_msg = [m for m in messages if m.get("role") == "system"]
            compressed = system_msg + [{"role": "summary", "content": summary}] + tail
        else:
            compressed = [{"role": "summary", "content": summary}] + tail

        logger.info(
            f"Compressed: {total_messages} -> {len(compressed)} messages "
            f"(summary: {len(summary)} chars)"
        )

        return compressed, summary

    def _generate_summary(
        self,
        messages: list[dict],
        model: Any,
        token_count: int,
    ) -> str:
        """Generate a summary of messages."""
        # If we have a previous summary, update it
        if self._previous_summary:
            return self._update_summary(messages, model)

        # Generate new summary
        if model:
            try:
                content = "\n".join(
                    f"{m.get('role', 'unknown')}: {m.get('content', '')}"
                    for m in messages
                    if m.get('content')
                )

                # Use model to summarize
                prompt = f"""Summarize this conversation concisely, preserving key information:

{content[:8000]}

Provide a structured summary with:
- Main topics discussed
- Key decisions made
- Important information
- Current state"""

                # This is a placeholder - use actual model in production
                summary = f"[Summary of {len(messages)} messages, ~{token_count} tokens]"
                self._previous_summary = summary
                return summary

            except Exception as e:
                logger.error(f"Summary generation failed: {e}")

        # Fallback summary
        summary = f"[Conversation summary: {len(messages)} messages]"
        self._previous_summary = summary
        return summary

    def _update_summary(self, new_messages: list[dict], model: Any) -> str:
        """Update existing summary with new messages."""
        if model:
            try:
                prompt = f"""Update this summary with new information:

Previous summary:
{self._previous_summary}

New messages:
{chr(10).join(m.get('content', '')[:500] for m in new_messages if m.get('content'))[:2000]}

Provide an updated summary:"""

                # Placeholder - use actual model in production
                updated = f"{self._previous_summary} [Updated with {len(new_messages)} new messages]"
                self._previous_summary = updated
                return updated

            except Exception as e:
                logger.error(f"Summary update failed: {e}")

        return self._previous_summary or ""

    def clear_cache(self) -> None:
        """Clear the summary cache."""
        self._previous_summary = None

    def get_stats(self) -> dict:
        """Get compression statistics."""
        return {
            "enabled": self.config.enabled,
            "threshold": self.config.threshold,
            "has_cached_summary": self._previous_summary is not None,
        }
