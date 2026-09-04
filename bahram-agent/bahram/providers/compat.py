from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from bahram.core.engine import AgentResponse
from bahram.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(BaseProvider):
    def __init__(
        self, api_key: str = "", model: str = "", base_url: str = "", **kwargs: Any
    ) -> None:
        super().__init__(api_key=api_key, model=model, **kwargs)
        self.base_url = base_url.rstrip("/")
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_tokens = kwargs.get("max_tokens", 4096)

    async def _call_api(
        self,
        messages: list[dict],
        system_msg: str,
        tools: list[dict],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> AgentResponse:
        import httpx

        api_messages = []
        if system_msg:
            api_messages.append({"role": "system", "content": system_msg})
        api_messages.extend(messages)
        payload: dict[str, Any] = {
            "model": self._get_model(model),
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120.0,
                )
                if response.status_code == 200:
                    return self._parse_openai_response(response.json())
                error = response.json().get("error", {}).get("message", "Unknown error")
                raise RuntimeError(f"API error ({response.status_code}): {error}")
        except ImportError:
            raise ImportError("httpx not installed. Run: pip install httpx")

    async def _stream_api(
        self,
        messages: list[dict],
        system_msg: str,
        tools: list[dict],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        import httpx

        api_messages = []
        if system_msg:
            api_messages.append({"role": "system", "content": system_msg})
        api_messages.extend(messages)
        payload: dict[str, Any] = {
            "model": self._get_model(model),
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=120.0,
                ) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                                delta = chunk["choices"][0].get("delta", {})
                                if "content" in delta and delta["content"]:
                                    yield delta["content"]
                            except (json.JSONDecodeError, KeyError, IndexError):
                                pass
        except ImportError:
            raise ImportError("httpx not installed. Run: pip install httpx")
