from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from bahram.core.engine import AgentResponse, ToolCall
from bahram.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    BASE_URL = "https://api.anthropic.com/v1"

    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        super().__init__(api_key=api_key, model=model or "claude-sonnet-4-20250514", **kwargs)
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_tokens = kwargs.get("max_tokens", 4096)

    async def _call_api(
        self,
        messages: list[dict],
        system_msg: str,
        tools: list[dict[str, Any]],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> AgentResponse:
        import httpx

        anthropic_msgs = self._convert_messages(messages)

        payload: dict[str, Any] = {
            "model": self._get_model(model),
            "messages": anthropic_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_msg:
            payload["system"] = system_msg
        if tools:
            payload["tools"] = self._convert_tools(tools)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=120.0,
                )
                if response.status_code == 200:
                    return self._parse_anthropic_response(response.json())
                error = response.json().get("error", {}).get("message", "Unknown error")
                raise RuntimeError(f"Anthropic API error ({response.status_code}): {error}")
        except ImportError:
            raise ImportError("httpx not installed. Run: pip install httpx")

    async def _stream_api(
        self,
        messages: list[dict],
        system_msg: str,
        tools: list[dict[str, Any]],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        import httpx

        anthropic_msgs = self._convert_messages(messages)

        payload: dict[str, Any] = {
            "model": self._get_model(model),
            "messages": anthropic_msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if system_msg:
            payload["system"] = system_msg

        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.BASE_URL}/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=120.0,
                ) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            try:
                                event = json.loads(data)
                                if event.get("type") == "content_block_delta":
                                    delta = event.get("delta", {})
                                    if delta.get("type") == "text_delta":
                                        yield delta.get("text", "")
                            except (json.JSONDecodeError, KeyError):
                                pass
        except ImportError:
            raise ImportError("httpx not installed. Run: pip install httpx")

    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        anthropic_msgs = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "tool":
                anthropic_msgs.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.get("tool_call_id", ""),
                                "content": msg.get("content", ""),
                            }
                        ],
                    }
                )
            elif role == "assistant":
                content_parts = []
                if msg.get("content"):
                    content_parts.append({"type": "text", "text": msg["content"]})
                for tc in msg.get("tool_calls", []):
                    func = tc.get("function", {})
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}
                    content_parts.append(
                        {
                            "type": "tool_use",
                            "id": tc.get("id", ""),
                            "name": func.get("name", ""),
                            "input": args,
                        }
                    )
                anthropic_msgs.append(
                    {
                        "role": "assistant",
                        "content": content_parts if content_parts else msg.get("content", ""),
                    }
                )
            else:
                anthropic_msgs.append({"role": role, "content": msg.get("content", "")})
        return anthropic_msgs

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        converted = []
        for t in tools:
            func = t.get("function", t)
            converted.append(
                {
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {}),
                }
            )
        return converted

    def _parse_anthropic_response(self, data: dict) -> AgentResponse:
        content_parts = data.get("content", [])
        text_parts = []
        tool_calls = []
        for part in content_parts:
            if part.get("type") == "text":
                text_parts.append(part.get("text", ""))
            elif part.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=part.get("id", f"call_{int(time.time() * 1000)}"),
                        name=part.get("name", ""),
                        arguments=part.get("input", {}),
                    )
                )
        return AgentResponse(content="\n".join(text_parts), tool_calls=tool_calls)

    def get_models(self) -> list[str]:
        return [
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
        ]

    def get_provider_info(self) -> dict[str, Any]:
        return {"name": "anthropic", "configured": bool(self.api_key), "model": self.model}
