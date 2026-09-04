from __future__ import annotations

from typing import Any

from bahram.providers.compat import OpenAICompatibleProvider


class ZhipuProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        super().__init__(
            api_key=api_key,
            model=model or "glm-4",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            **kwargs,
        )

    def get_models(self) -> list[str]:
        return ["glm-4", "glm-3-turbo"]

    def get_provider_info(self) -> dict[str, Any]:
        return {"name": "zhipu", "configured": bool(self.api_key), "model": self.model}
