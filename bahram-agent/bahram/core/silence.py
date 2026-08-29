"""Silence tokens for Bahram Agent."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SilenceManager:
    """Manage silence tokens for voice TTS."""

    def __init__(self) -> None:
        self._tokens: dict[str, str] = {
            "pause": "...",
            "short_pause": ".",
            "long_pause": "...",
            "break": "\n",
            "emphasis": "**",
            "whisper": "*",
            "normal": "",
        }
        self._custom_tokens: dict[str, str] = {}

    def get_token(self, name: str) -> str:
        """Get a silence token."""
        return self._custom_tokens.get(name, self._tokens.get(name, ""))

    def add_token(self, name: str, value: str) -> None:
        """Add a custom silence token."""
        self._custom_tokens[name] = value

    def remove_token(self, name: str) -> bool:
        """Remove a custom silence token."""
        if name in self._custom_tokens:
            del self._custom_tokens[name]
            return True
        return False

    def list_tokens(self) -> dict[str, str]:
        """List all tokens."""
        all_tokens = self._tokens.copy()
        all_tokens.update(self._custom_tokens)
        return all_tokens

    def apply_tokens(self, text: str) -> str:
        """Apply silence tokens to text."""
        result = text
        for name, value in self._list_all_tokens().items():
            token = f"[{name}]"
            result = result.replace(token, value)
        return result

    def _list_all_tokens(self) -> dict[str, str]:
        """List all tokens."""
        all_tokens = self._tokens.copy()
        all_tokens.update(self._custom_tokens)
        return all_tokens
