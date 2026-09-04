"""
Silence.

Public objects: ``SilenceManager``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class SilenceManager:
    """
    Silence manager.
    """

    def __init__(self) -> None:
        """
        Initialise a SilenceManager instance.
        """
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
        """
        Return the token.

        Args:
            name (str): name of the object.

        Returns:
            str: the rendered string.
        """
        return self._custom_tokens.get(name, self._tokens.get(name, ""))

    def add_token(self, name: str, value: str) -> None:
        """
        Add token.

        Args:
            name (str): name of the object.
            value (str): value string.
        """
        self._custom_tokens[name] = value

    def remove_token(self, name: str) -> bool:
        """
        Remove token.

        Args:
            name (str): name of the object.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        if name in self._custom_tokens:
            del self._custom_tokens[name]
            return True
        return False

    def list_tokens(self) -> dict[str, str]:
        """
        List tokens.

        Returns:
            dict[str, str]: a mapping of str, str.
        """
        all_tokens = self._tokens.copy()
        all_tokens.update(self._custom_tokens)
        return all_tokens

    def apply_tokens(self, text: str) -> str:
        """
        Apply tokens.

        Args:
            text (str): text string.

        Returns:
            str: the rendered string.
        """
        result = text
        for name, value in self._list_all_tokens().items():
            token = f"[{name}]"
            result = result.replace(token, value)
        return result

    def _list_all_tokens(self) -> dict[str, str]:
        all_tokens = self._tokens.copy()
        all_tokens.update(self._custom_tokens)
        return all_tokens
