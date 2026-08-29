"""LM Studio provider."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from bahram.core.engine import AgentResponse, Message, MessageRole, ToolCall
from bahram.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class LMStudioProvider(BaseProvider):
    """LM Studio provider for local models."""

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AgentResponse:
        """Generate a completion using LM Studio API."""
        try:
            import httpx

            base_url = self.config.base_url or "http://localhost:1234/v1"

            # Convert messages
            openai_messages = []
            for msg in messages:
                openai_messages.append(
                    {"role": msg.role.value, "content": msg.content}
                )

            # Prepare request
            payload = {
                "model": kwargs.get("model", "local-model"),
                "messages": openai_messages,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "temperature": kwargs.get("temperature", 0.7),
            }

            if tools:
                payload["tools"] = tools

            # Make request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=120.0,
                )

                if response.status_code != 200:
                    raise Exception(f"LM Studio error: {response.text}")

                data = response.json()
                choice = data["choices"][0]
                message = choice["message"]

                content = message.get("content", "") or ""
                tool_calls = []

                if "tool_calls" in message:
                    for tc in message["tool_calls"]:
                        tool_calls.append(
                            ToolCall(
                                id=tc["id"],
                                name=tc["function"]["name"],
                                arguments=json.loads(tc["function"]["arguments"]),
                            )
                        )

                return AgentResponse(
                    content=content,
                    tool_calls=tool_calls,
                    metadata={"usage": data.get("usage", {})},
                )

        except ImportError:
            raise Exception("httpx not installed")
        except Exception as e:
            logger.error(f"LM Studio API error: {e}")
            raise

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion using LM Studio API."""
        try:
            import httpx

            base_url = self.config.base_url or "http://localhost:1234/v1"

            openai_messages = []
            for msg in messages:
                openai_messages.append(
                    {"role": msg.role.value, "content": msg.content}
                )

            payload = {
                "model": kwargs.get("model", "local-model"),
                "messages": openai_messages,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "stream": True,
            }

            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=120.0,
                ) as response:
                    if response.status_code != 200:
                        raise Exception(f"LM Studio stream error: {response.status_code}")

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = json.loads(line[6:])
                            if data["choices"][0]["delta"].get("content"):
                                yield data["choices"][0]["delta"]["content"]

        except Exception as e:
            logger.error(f"LM Studio stream error: {e}")
            raise
