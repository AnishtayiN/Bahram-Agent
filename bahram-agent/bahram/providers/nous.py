from __future__ import annotations

from typing import Any

from bahram.providers.compat import OpenAICompatibleProvider


class NousProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        super().__init__(
            api_key=api_key,
            model=model or "nous-hermes-2-mixtral-8x7b-dpo",
            base_url="https://api.nousresearch.com/v1",
            **kwargs,
        )

    def get_models(self) -> list[str]:
        return ["nous-hermes-2-mixtral-8x7b-dpo", "nous-hermes-2-yi-34b"]

    def get_provider_info(self) -> dict[str, Any]:
        return {"name": "nous", "configured": bool(self.api_key), "model": self.model}
