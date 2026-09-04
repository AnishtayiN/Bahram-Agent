"""
Google.

Public objects: ``GoogleProvider``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from bahram.core.engine import AgentResponse
from bahram.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class GoogleProvider(BaseProvider):
    """
    Google provider.
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        """
        Initialise a GoogleProvider instance.

        Args:
            api_key (str): api key string. Defaults to ``''``.
            model (str): model identifier in ``provider/model`` form. Defaults to ``''``.
            **kwargs (Any): keyword arguments forwarded to the implementation.
        """
        super().__init__(api_key=api_key, model=model or "gemini-1.5-flash", **kwargs)
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

        contents = []
        if system_msg:
            contents.append({"role": "user", "parts": [{"text": system_msg}]})
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})
        for msg in messages:
            role = "user" if msg.get("role") in ("user", "tool") else "model"
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                contents.append({"role": role, "parts": [{"text": content}]})
        model_name = self._get_model(model)
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        if tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": t.get("function", t).get("name", ""),
                            "description": t.get("function", t).get("description", ""),
                            "parameters": t.get("function", t).get("parameters", {}),
                        }
                        for t in tools
                    ]
                }
            ]
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/models/{model_name}:generateContent?key={self.api_key}",
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=120.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        text = " ".join(p.get("text", "") for p in parts if "text" in p)
                        return AgentResponse(content=text)
                    return AgentResponse(content="")
                error = response.json().get("error", {}).get("message", "Unknown error")
                raise RuntimeError(f"Google API error ({response.status_code}): {error}")
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

        contents = []
        if system_msg:
            contents.append({"role": "user", "parts": [{"text": system_msg}]})
            contents.append({"role": "model", "parts": [{"text": "Understood."}]})
        for msg in messages:
            role = "user" if msg.get("role") in ("user", "tool") else "model"
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                contents.append({"role": role, "parts": [{"text": content}]})
        model_name = self._get_model(model)
        payload = {
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.BASE_URL}/models/{model_name}:streamGenerateContent?key={self.api_key}",
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=120.0,
                ) as response:
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                chunk = json.loads(line)
                                candidates = chunk.get("candidates", [])
                                if candidates:
                                    parts = candidates[0].get("content", {}).get("parts", [])
                                    for p in parts:
                                        if "text" in p:
                                            yield p["text"]
                            except json.JSONDecodeError:
                                pass
        except ImportError:
            raise ImportError("httpx not installed. Run: pip install httpx")

    def get_models(self) -> list[str]:
        """
        Return the models.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        return ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]

    def get_provider_info(self) -> dict[str, Any]:
        """
        Return the provider info.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {"name": "google", "configured": bool(self.api_key), "model": self.model}
