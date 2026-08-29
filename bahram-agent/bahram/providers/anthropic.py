"""Anthropic provider."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from bahram.core.engine import AgentResponse, Message, MessageRole, ToolCall
from bahram.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    """Anthropic Claude provider."""

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AgentResponse:
        """Generate a completion using Anthropic API."""
        try:
            import httpx

            api_key = self.config.api_key
            if not api_key:
                raise ValueError("Anthropic API key not configured")

            # Convert messages to Anthropic format
            system_msg = ""
            anthropic_messages = []

            for msg in messages:
                if msg.role == MessageRole.SYSTEM:
                    system_msg = msg.content
                elif msg.role in (MessageRole.USER, MessageRole.ASSISTANT):
                    anthropic_messages.append(
                        {"role": msg.role.value, "content": msg.content}
                    )

            # Prepare request
            payload = {
                "model": kwargs.get("model", "claude-sonnet-4-6"),
                "max_tokens": kwargs.get("max_tokens", 4096),
                "messages": anthropic_messages,
            }

            if system_msg:
                payload["system"] = system_msg

            if tools:
                payload["tools"] = self._convert_tools(tools)

            # Make request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=payload,
                    timeout=60.0,
                )

                if response.status_code != 200:
                    error = response.json().get("error", {})
                    raise Exception(f"API error: {error.get('message', 'Unknown error')}")

                data = response.json()

                # Parse response
                content = ""
                tool_calls = []

                for block in data.get("content", []):
                    if block["type"] == "text":
                        content += block["text"]
                    elif block["type"] == "tool_use":
                        tool_calls.append(
                            ToolCall(
                                id=block["id"],
                                name=block["name"],
                                arguments=block["input"],
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
            logger.error(f"Anthropic API error: {e}")
            raise

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion using Anthropic API."""
        try:
            import httpx

            api_key = self.config.api_key
            if not api_key:
                raise ValueError("Anthropic API key not configured")

            # Convert messages
            system_msg = ""
            anthropic_messages = []

            for msg in messages:
                if msg.role == MessageRole.SYSTEM:
                    system_msg = msg.content
                elif msg.role in (MessageRole.USER, MessageRole.ASSISTANT):
                    anthropic_messages.append(
                        {"role": msg.role.value, "content": msg.content}
                    )

            # Prepare request
            payload = {
                "model": kwargs.get("model", "claude-sonnet-4-6"),
                "max_tokens": kwargs.get("max_tokens", 4096),
                "messages": anthropic_messages,
                "stream": True,
            }

            if system_msg:
                payload["system"] = system_msg

            if tools:
                payload["tools"] = self._convert_tools(tools)

            # Stream request
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=payload,
                    timeout=60.0,
                ) as response:
                    if response.status_code != 200:
                        raise Exception(f"Stream error: {response.status_code}")

                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = json.loads(line[6:])
                            if data["type"] == "content_block_delta":
                                if data["delta"]["type"] == "text_delta":
                                    yield data["delta"]["text"]

        except Exception as e:
            logger.error(f"Anthropic stream error: {e}")
            raise

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert tools to Anthropic format."""
        converted = []
        for tool in tools:
            if "function" in tool:
                func = tool["function"]
                converted.append(
                    {
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {}),
                    }
                )
        return converted
