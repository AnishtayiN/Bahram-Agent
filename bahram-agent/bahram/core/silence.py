from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

class SilenceManager:

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
        return self._custom_tokens.get(name, self._tokens.get(name, ""))

    def add_token(self, name: str, value: str) -> None:
        self._custom_tokens[name] = value

    def remove_token(self, name: str) -> bool:
        if name in self._custom_tokens:
            del self._custom_tokens[name]
            return True
        return False

    def list_tokens(self) -> dict[str, str]:
        all_tokens = self._tokens.copy()
        all_tokens.update(self._custom_tokens)
        return all_tokens

    def apply_tokens(self, text: str) -> str:
        result = text
        for name, value in self._list_all_tokens().items():
            token = f"[{name}]"
            result = result.replace(token, value)
        return result

    def _list_all_tokens(self) -> dict[str, str]:
        all_tokens = self._tokens.copy()
        all_tokens.update(self._custom_tokens)
        return all_tokens
