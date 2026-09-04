from __future__ import annotations

from typing import Any

from bahram.providers.compat import OpenAICompatibleProvider


class OpenRouterProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        super().__init__(api_key=api_key, model=model or "anthropic/claude-3.5-sonnet", base_url="https://openrouter.ai/api/v1", **kwargs)

    def get_models(self) -> list[str]:
        return ["anthropic/claude-3.5-sonnet", "openai/gpt-4o", "meta-llama/llama-3-70b"]

    def get_provider_info(self) -> dict[str, Any]:
        return {"name": "openrouter", "configured": bool(self.api_key), "model": self.model}
