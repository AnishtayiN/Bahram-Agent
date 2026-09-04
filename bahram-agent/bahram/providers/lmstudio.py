from __future__ import annotations

from typing import Any

from bahram.providers.compat import OpenAICompatibleProvider


class LMStudioProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str = "", model: str = "", base_url: str = "", **kwargs: Any) -> None:
        super().__init__(api_key=api_key, model=model or "default", base_url=base_url or "http://localhost:1234/v1", **kwargs)

    def get_models(self) -> list[str]:
        return ["default"]

    def get_provider_info(self) -> dict[str, Any]:
        return {"name": "lmstudio", "configured": True, "model": self.model}
