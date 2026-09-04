from __future__ import annotations

from typing import Any

from bahram.providers.compat import OpenAICompatibleProvider


class MiniMaxProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        super().__init__(api_key=api_key, model=model or "abab6.5-chat", base_url="https://api.minimax.chat/v1", **kwargs)

    def get_models(self) -> list[str]:
        return ["abab6.5-chat", "abab5.5-chat"]

    def get_provider_info(self) -> dict[str, Any]:
        return {"name": "minimax", "configured": bool(self.api_key), "model": self.model}
