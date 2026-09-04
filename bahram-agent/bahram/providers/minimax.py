"""
Minimax.

Public objects: ``MiniMaxProvider``.
"""

from __future__ import annotations

from typing import Any

from bahram.providers.compat import OpenAICompatibleProvider


class MiniMaxProvider(OpenAICompatibleProvider):
    """
    Mini max provider.
    """

    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        """
        Initialise a MiniMaxProvider instance.

        Args:
            api_key (str): api key string. Defaults to ``''``.
            model (str): model identifier in ``provider/model`` form. Defaults to ``''``.
            **kwargs (Any): keyword arguments forwarded to the implementation.
        """
        super().__init__(
            api_key=api_key,
            model=model or "abab6.5-chat",
            base_url="https://api.minimax.chat/v1",
            **kwargs,
        )

    def get_models(self) -> list[str]:
        """
        Return the models.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        return ["abab6.5-chat", "abab5.5-chat"]

    def get_provider_info(self) -> dict[str, Any]:
        """
        Return the provider info.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {"name": "minimax", "configured": bool(self.api_key), "model": self.model}
