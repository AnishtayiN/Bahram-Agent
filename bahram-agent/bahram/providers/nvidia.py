"""
Nvidia.

Public objects: ``NvidiaProvider``.
"""

from __future__ import annotations

from typing import Any

from bahram.providers.compat import OpenAICompatibleProvider


class NvidiaProvider(OpenAICompatibleProvider):
    """
    Nvidia provider.
    """

    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        """
        Initialise a NvidiaProvider instance.

        Args:
            api_key (str): api key string. Defaults to ``''``.
            model (str): model identifier in ``provider/model`` form. Defaults to ``''``.
            **kwargs (Any): keyword arguments forwarded to the implementation.
        """
        super().__init__(
            api_key=api_key,
            model=model or "nvidia/llama-3.1-nemotron-70b-instruct",
            base_url="https://integrate.api.nvidia.com/v1",
            **kwargs,
        )

    def get_models(self) -> list[str]:
        """
        Return the models.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        return ["nvidia/llama-3.1-nemotron-70b-instruct", "nvidia/mistral-nemo-12b-instruct"]

    def get_provider_info(self) -> dict[str, Any]:
        """
        Return the provider info.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {"name": "nvidia", "configured": bool(self.api_key), "model": self.model}
