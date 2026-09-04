"""
Xiaomi.

Public objects: ``XiaomiProvider``.
"""

from __future__ import annotations

from typing import Any

from bahram.providers.compat import OpenAICompatibleProvider


class XiaomiProvider(OpenAICompatibleProvider):
    """
    Xiaomi provider.
    """

    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        """
        Initialise a XiaomiProvider instance.

        Args:
            api_key (str): api key string. Defaults to ``''``.
            model (str): model identifier in ``provider/model`` form. Defaults to ``''``.
            **kwargs (Any): keyword arguments forwarded to the implementation.
        """
        super().__init__(
            api_key=api_key,
            model=model or "MiLM-6B",
            base_url="https://api.xiaomi.com/v1",
            **kwargs,
        )

    def get_models(self) -> list[str]:
        """
        Return the models.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        return ["MiLM-6B"]

    def get_provider_info(self) -> dict[str, Any]:
        """
        Return the provider info.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {"name": "xiaomi", "configured": bool(self.api_key), "model": self.model}
