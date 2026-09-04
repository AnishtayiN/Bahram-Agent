from __future__ import annotations

from typing import Any

from bahram.providers.compat import OpenAICompatibleProvider


class KimiProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        super().__init__(api_key=api_key, model=model or "moonshot-v1-8k", base_url="https://api.moonshot.cn/v1", **kwargs)

    def get_models(self) -> list[str]:
        return ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]

    def get_provider_info(self) -> dict[str, Any]:
        return {"name": "kimi", "configured": bool(self.api_key), "model": self.model}
