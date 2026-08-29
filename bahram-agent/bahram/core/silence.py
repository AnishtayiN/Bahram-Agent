"""Silence tokens for Bahram Agent."""

from __future__ import annotations

SILENCE_TOKENS = [
    "[SILENT]",
    "SILENT",
    "NO_REPLY",
    "NO REPLY",
]


def is_silence_token(text: str) -> bool:
    """Check if text is a silence token."""
    normalized = text.strip()
    # Case-insensitive comparison
    upper = normalized.upper()
    for token in SILENCE_TOKENS:
        if upper == token.upper():
            return True
    return False


def should_suppress_response(text: str) -> bool:
    """Check if response should be suppressed."""
    return is_silence_token(text)
