"""Custom endpoint provider."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from bahram.core.engine import AgentResponse, Message, MessageRole, ToolCall
from bahram.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class CustomProvider(BaseProvider):
    """Custom endpoint provider for any OpenAI-compatible API."""

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AgentResponse:
        """Generate a completion using custom endpoint."""
        try:
            import httpx

            api_key = self.config.api_key
            base_url = self.config.base_url

            if not base_url:
                raise ValueError("Custom endpoint URL not configured")

            # Convert messages
            openai_messages = []
            for msg in messages:
                openai_messages.append(
                    {"role": msg.role.value, "content": msg.content}
                )

            # Prepare request
            payload = {
                "model": kwargs.get("model", "default"),
                "messages": openai_messages,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "temperature": kwargs.get("temperature", 0.7),
            }

            if tools:
                payload["tools"] = tools

            # Prepare headers
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            # Make request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60.0,
                )

                if response.status_code != 200:
                    raise Exception(f"API error: {response.text}")

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
            logger.error(f"Custom endpoint error: {e}")
            raise

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion using custom endpoint."""
        try:
            import httpx

            api_key = self.config.api_key
            base_url = self.config.base_url

            if not base_url:
                raise ValueError("Custom endpoint URL not configured")

            openai_messages = []
            for msg in messages:
                openai_messages.append(
                    {"role": msg.role.value, "content": msg.content}
                )

            payload = {
                "model": kwargs.get("model", "default"),
                "messages": openai_messages,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "stream": True,
            }

            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60.0,
                ) as response:
                    if response.status_code != 200:
                        raise Exception(f"Stream error: {response.status_code}")

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = json.loads(line[6:])
                            if data["choices"][0]["delta"].get("content"):
                                yield data["choices"][0]["delta"]["content"]

        except Exception as e:
            logger.error(f"Custom endpoint stream error: {e}")
            raise
