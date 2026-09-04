from __future__ import annotations

from typing import Any

from bahram.providers.compat import OpenAICompatibleProvider


class XiaomiProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        super().__init__(
            api_key=api_key,
            model=model or "MiLM-6B",
            base_url="https://api.xiaomi.com/v1",
            **kwargs,
        )

    def get_models(self) -> list[str]:
        return ["MiLM-6B"]

    def get_provider_info(self) -> dict[str, Any]:
        return {"name": "xiaomi", "configured": bool(self.api_key), "model": self.model}
