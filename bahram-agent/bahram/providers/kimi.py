from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from bahram.core.engine import AgentResponse, Message, MessageRole, ToolCall
from bahram.providers.base import BaseProvider

logger = logging.getLogger(__name__)

class KimiProvider(BaseProvider):
    ""

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AgentResponse:
        ""
        try:
            import httpx

            api_key = self.config.api_key
            base_url = self.config.base_url or "https://api.moonshot.cn/v1"

            if not api_key:
                raise ValueError("Kimi API key not configured")

            openai_messages = []
            for msg in messages:
                openai_messages.append(
                    {"role": msg.role.value, "content": msg.content}
                )

            payload = {
                "model": kwargs.get("model", "moonshot-v1-128k"),
                "messages": openai_messages,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "temperature": kwargs.get("temperature", 0.7),
            }

            if tools:
                payload["tools"] = tools

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
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
            logger.error(f"Kimi API error: {e}")
            raise

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        ""
        try:
            import httpx

            api_key = self.config.api_key
            base_url = self.config.base_url or "https://api.moonshot.cn/v1"

            if not api_key:
                raise ValueError("Kimi API key not configured")

            openai_messages = []
            for msg in messages:
                openai_messages.append(
                    {"role": msg.role.value, "content": msg.content}
                )

            payload = {
                "model": kwargs.get("model", "moonshot-v1-128k"),
                "messages": openai_messages,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "stream": True,
            }

            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
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
            logger.error(f"Kimi stream error: {e}")
            raise
