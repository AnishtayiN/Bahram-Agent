from __future__ import annotations

from typing import Any

from bahram.providers.compat import OpenAICompatibleProvider


class HuggingFaceProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        super().__init__(api_key=api_key, model=model or "meta-llama/Meta-Llama-3.1-8B-Instruct", base_url="https://api-inference.huggingface.co/v1", **kwargs)

    def get_models(self) -> list[str]:
        return ["meta-llama/Meta-Llama-3.1-8B-Instruct"]

    def get_provider_info(self) -> dict[str, Any]:
        return {"name": "huggingface", "configured": bool(self.api_key), "model": self.model}
