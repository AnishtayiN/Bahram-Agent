"""OpenAI provider."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from bahram.core.engine import AgentResponse, Message, MessageRole, ToolCall
from bahram.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    """OpenAI GPT provider."""

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AgentResponse:
        """Generate a completion using OpenAI API."""
        try:
            import httpx

            api_key = self.config.api_key
            if not api_key:
                raise ValueError("OpenAI API key not configured")

            # Convert messages to OpenAI format
            openai_messages = []
            for msg in messages:
                openai_messages.append(
                    {"role": msg.role.value, "content": msg.content}
                )

            # Prepare request
            payload = {
                "model": kwargs.get("model", "gpt-4o"),
                "messages": openai_messages,
                "max_tokens": kwargs.get("max_tokens", 4096),
            }

            if tools:
                payload["tools"] = tools

            # Make request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=60.0,
                )

                if response.status_code != 200:
                    error = response.json().get("error", {})
                    raise Exception(f"API error: {error.get('message', 'Unknown error')}")

                data = response.json()
                choice = data["choices"][0]
                message = choice["message"]

                # Parse response
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
            raise Exception("httpx not installed. Install with: pip install httpx")
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion using OpenAI API."""
        try:
            import httpx

            api_key = self.config.api_key
            if not api_key:
                raise ValueError("OpenAI API key not configured")

            # Convert messages
            openai_messages = []
            for msg in messages:
                openai_messages.append(
                    {"role": msg.role.value, "content": msg.content}
                )

            # Prepare request
            payload = {
                "model": kwargs.get("model", "gpt-4o"),
                "messages": openai_messages,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "stream": True,
            }

            if tools:
                payload["tools"] = tools

            # Stream request
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
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
            logger.error(f"OpenAI stream error: {e}")
            raise
