"""
Groq.

Public objects: ``GroqProvider``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from bahram.core.engine import AgentResponse
from bahram.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class GroqProvider(BaseProvider):
    """
    Groq provider.
    """

    BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        """
        Initialise a GroqProvider instance.

        Args:
            api_key (str): api key string. Defaults to ``''``.
            model (str): model identifier in ``provider/model`` form. Defaults to ``''``.
            **kwargs (Any): keyword arguments forwarded to the implementation.
        """
        super().__init__(api_key=api_key, model=model or "llama3-8b-8192", **kwargs)
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
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=60.0,
                )
                if response.status_code == 200:
                    return self._parse_openai_response(response.json())
                error = response.json().get("error", {}).get("message", "Unknown error")
                raise RuntimeError(f"Groq API error ({response.status_code}): {error}")
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
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.BASE_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=60.0,
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

    def get_models(self) -> list[str]:
        """
        Return the models.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        return ["llama3-8b-8192", "llama3-70b-8192", "mixtral-8x7b-32768", "gemma-7b-it"]

    def get_provider_info(self) -> dict[str, Any]:
        """
        Return the provider info.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {"name": "groq", "configured": bool(self.api_key), "model": self.model}
