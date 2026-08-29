"""Ollama provider for local models."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from bahram.core.engine import AgentResponse, Message, MessageRole, ToolCall
from bahram.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseProvider):
    """Ollama provider for local models."""

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AgentResponse:
        """Generate a completion using Ollama API."""
        try:
            import httpx

            base_url = self.config.base_url or "http://localhost:11434"

            # Convert messages
            ollama_messages = []
            for msg in messages:
                ollama_messages.append(
                    {"role": msg.role.value, "content": msg.content}
                )

            # Prepare request
            payload = {
                "model": kwargs.get("model", "llama3.1"),
                "messages": ollama_messages,
                "stream": False,
                "options": {
                    "num_predict": kwargs.get("max_tokens", 4096),
                    "temperature": kwargs.get("temperature", 0.7),
                },
            }

            if tools:
                payload["tools"] = tools

            # Make request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base_url}/api/chat",
                    json=payload,
                    timeout=120.0,
                )

                if response.status_code != 200:
                    raise Exception(f"Ollama error: {response.text}")

                data = response.json()
                message = data.get("message", {})

                # Parse response
                content = message.get("content", "")
                tool_calls = []

                if "tool_calls" in message:
                    for tc in message["tool_calls"]:
                        func = tc.get("function", {})
                        tool_calls.append(
                            ToolCall(
                                id=f"call_{len(tool_calls)}",
                                name=func.get("name", ""),
                                arguments=func.get("arguments", {}),
                            )
                        )

                return AgentResponse(
                    content=content,
                    tool_calls=tool_calls,
                    metadata={"eval_count": data.get("eval_count", 0)},
                )

        except ImportError:
            raise Exception("httpx not installed")
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            raise

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion using Ollama API."""
        try:
            import httpx

            base_url = self.config.base_url or "http://localhost:11434"

            ollama_messages = []
            for msg in messages:
                ollama_messages.append(
                    {"role": msg.role.value, "content": msg.content}
                )

            payload = {
                "model": kwargs.get("model", "llama3.1"),
                "messages": ollama_messages,
                "stream": True,
                "options": {
                    "num_predict": kwargs.get("max_tokens", 4096),
                    "temperature": kwargs.get("temperature", 0.7),
                },
            }

            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/api/chat",
                    json=payload,
                    timeout=120.0,
                ) as response:
                    if response.status_code != 200:
                        raise Exception(f"Ollama stream error: {response.status_code}")

                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                if data.get("message", {}).get("content"):
                                    yield data["message"]["content"]
                            except json.JSONDecodeError:
                                continue

        except Exception as e:
            logger.error(f"Ollama stream error: {e}")
            raise
