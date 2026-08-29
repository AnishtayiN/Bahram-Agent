from __future__ import annotations
from typing import Any
from bahram.providers.compat import OpenAICompatibleProvider

class NvidiaProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        super().__init__(api_key=api_key, model=model or "nvidia/llama-3.1-nemotron-70b-instruct", base_url="https://integrate.api.nvidia.com/v1", **kwargs)

    def get_models(self) -> list[str]:
        return ["nvidia/llama-3.1-nemotron-70b-instruct", "nvidia/mistral-nemo-12b-instruct"]

    def get_provider_info(self) -> dict[str, Any]:
        return {"name": "nvidia", "configured": bool(self.api_key), "model": self.model}
