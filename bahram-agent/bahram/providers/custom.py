"""
Custom.

Public objects: ``CustomProvider``.
"""

from __future__ import annotations

from typing import Any

from bahram.providers.compat import OpenAICompatibleProvider


class CustomProvider(OpenAICompatibleProvider):
    """
    Custom provider.
    """

    def __init__(
        self, api_key: str = "", model: str = "", base_url: str = "", **kwargs: Any
    ) -> None:
        """
        Initialise a CustomProvider instance.

        Args:
            api_key (str): api key string. Defaults to ``''``.
            model (str): model identifier in ``provider/model`` form. Defaults to ``''``.
            base_url (str): base url string. Defaults to ``''``.
            **kwargs (Any): keyword arguments forwarded to the implementation.
        """
        super().__init__(api_key=api_key, model=model, base_url=base_url, **kwargs)

    def get_models(self) -> list[str]:
        """
        Return the models.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        return [self.model] if self.model else []

    def get_provider_info(self) -> dict[str, Any]:
        """
        Return the provider info.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {
            "name": "custom",
            "configured": bool(self.api_key),
            "model": self.model,
            "base_url": self.base_url,
        }
