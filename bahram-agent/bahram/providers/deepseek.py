from __future__ import annotations
from typing import Any
from bahram.providers.compat import OpenAICompatibleProvider

class DeepSeekProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        super().__init__(api_key=api_key, model=model or "deepseek-chat", base_url="https://api.deepseek.com", **kwargs)

    def get_models(self) -> list[str]:
        return ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"]

    def get_provider_info(self) -> dict[str, Any]:
        return {"name": "deepseek", "configured": bool(self.api_key), "model": self.model}
