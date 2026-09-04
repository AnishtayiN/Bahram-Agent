from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from bahram.core.engine import AgentResponse, ToolCall
from bahram.providers.base import BaseProvider

logger = logging.getLogger(__name__)

class OllamaProvider(BaseProvider):
    def __init__(self, api_key: str = "", model: str = "", base_url: str = "", **kwargs: Any) -> None:
        super().__init__(api_key=api_key, model=model or "llama3", **kwargs)
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_tokens = kwargs.get("max_tokens", 4096)

    async def _call_api(
        self, messages: list[dict], system_msg: str, tools: list[dict],
        model: str | None, temperature: float, max_tokens: int,
    ) -> AgentResponse:
        import httpx
        api_messages = []
        if system_msg:
            api_messages.append({"role": "system", "content": system_msg})
        api_messages.extend(messages)
        payload: dict[str, Any] = {
            "model": self._get_model(model),
            "messages": api_messages,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if tools:
            payload["tools"] = tools
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload, timeout=120.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    msg = data.get("message", {})
                    content = msg.get("content", "")
                    tool_calls_raw = msg.get("tool_calls") or []
                    tool_calls = []
                    for tc in tool_calls_raw:
                        func = tc.get("function", {})
                        tool_calls.append(ToolCall(
                            id=f"call_{len(tool_calls)}",
                            name=func.get("name", ""),
                            arguments=func.get("arguments", {}),
                        ))
                    return AgentResponse(content=content, tool_calls=tool_calls)
                raise RuntimeError(f"Ollama API error ({response.status_code}): {response.text}")
        except ImportError:
            raise ImportError("httpx not installed. Run: pip install httpx")

    async def _stream_api(
        self, messages: list[dict], system_msg: str, tools: list[dict],
        model: str | None, temperature: float, max_tokens: int,
    ) -> AsyncIterator[str]:
        import httpx
        api_messages = []
        if system_msg:
            api_messages.append({"role": "system", "content": system_msg})
        api_messages.extend(messages)
        payload: dict[str, Any] = {
            "model": self._get_model(model), "messages": api_messages,
            "stream": True, "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", f"{self.base_url}/api/chat",
                    json=payload, timeout=120.0) as response:
                    async for line in response.aiter_lines():
                        if line.strip():
                            try:
                                chunk = json.loads(line)
                                content = chunk.get("message", {}).get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                pass
        except ImportError:
            raise ImportError("httpx not installed. Run: pip install httpx")

    def get_models(self) -> list[str]:
        return ["llama3", "llama3.1", "codellama", "mistral"]

    def get_provider_info(self) -> dict[str, Any]:
        return {"name": "ollama", "configured": True, "model": self.model, "base_url": self.base_url}
