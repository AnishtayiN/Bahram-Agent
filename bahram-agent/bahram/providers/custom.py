from __future__ import annotations

from typing import Any

from bahram.providers.compat import OpenAICompatibleProvider


class CustomProvider(OpenAICompatibleProvider):
    def __init__(
        self, api_key: str = "", model: str = "", base_url: str = "", **kwargs: Any
    ) -> None:
        super().__init__(api_key=api_key, model=model, base_url=base_url, **kwargs)

    def get_models(self) -> list[str]:
        return [self.model] if self.model else []

    def get_provider_info(self) -> dict[str, Any]:
        return {
            "name": "custom",
            "configured": bool(self.api_key),
            "model": self.model,
            "base_url": self.base_url,
        }
