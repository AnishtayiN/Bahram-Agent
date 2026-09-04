from __future__ import annotations

from typing import Any

from bahram.providers.compat import OpenAICompatibleProvider


class MistralProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        super().__init__(
            api_key=api_key,
            model=model or "mistral-large-latest",
            base_url="https://api.mistral.ai/v1",
            **kwargs,
        )

    def get_models(self) -> list[str]:
        return ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest"]

    def get_provider_info(self) -> dict[str, Any]:
        return {"name": "mistral", "configured": bool(self.api_key), "model": self.model}
