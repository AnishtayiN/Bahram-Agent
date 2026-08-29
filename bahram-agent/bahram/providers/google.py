"""Google Gemini provider."""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from bahram.core.engine import AgentResponse, Message, MessageRole, ToolCall
from bahram.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class GoogleProvider(BaseProvider):
    """Google Gemini provider."""

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AgentResponse:
        """Generate a completion using Google Gemini API."""
        try:
            import httpx

            api_key = self.config.api_key
            base_url = self.config.base_url or "https://generativelanguage.googleapis.com/v1beta"

            if not api_key:
                raise ValueError("Google API key not configured")

            model = kwargs.get("model", "gemini-1.5-pro")

            # Convert messages to Gemini format
            contents = []
            for msg in messages:
                if msg.role == MessageRole.SYSTEM:
                    contents.append({"role": "user", "parts": [{"text": msg.content}]})
                else:
                    role = "user" if msg.role == MessageRole.USER else "model"
                    contents.append({"role": role, "parts": [{"text": msg.content}]})

            # Prepare request
            payload = {
                "contents": contents,
                "generationConfig": {
                    "maxOutputTokens": kwargs.get("max_tokens", 4096),
                    "temperature": kwargs.get("temperature", 0.7),
                },
            }

            if tools:
                payload["tools"] = [{"functionDeclarations": tools}]

            # Make request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{base_url}/models/{model}:generateContent?key={api_key}",
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=60.0,
                )

                if response.status_code != 200:
                    error = response.json().get("error", {})
                    raise Exception(f"API error: {error.get('message', 'Unknown error')}")

                data = response.json()
                candidate = data["candidates"][0]
                content = candidate["content"]

                # Parse response
                text = ""
                tool_calls = []

                for part in content.get("parts", []):
                    if "text" in part:
                        text += part["text"]
                    elif "functionCall" in part:
                        func = part["functionCall"]
                        tool_calls.append(
                            ToolCall(
                                id=f"call_{len(tool_calls)}",
                                name=func["name"],
                                arguments=func["args"],
                            )
                        )

                return AgentResponse(
                    content=text,
                    tool_calls=tool_calls,
                    metadata={"usage": data.get("usageMetadata", {})},
                )

        except ImportError:
            raise Exception("httpx not installed")
        except Exception as e:
            logger.error(f"Google Gemini API error: {e}")
            raise

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream a completion using Google Gemini API."""
        try:
            import httpx

            api_key = self.config.api_key
            base_url = self.config.base_url or "https://generativelanguage.googleapis.com/v1beta"

            if not api_key:
                raise ValueError("Google API key not configured")

            model = kwargs.get("model", "gemini-1.5-pro")

            contents = []
            for msg in messages:
                if msg.role == MessageRole.SYSTEM:
                    contents.append({"role": "user", "parts": [{"text": msg.content}]})
                else:
                    role = "user" if msg.role == MessageRole.USER else "model"
                    contents.append({"role": role, "parts": [{"text": msg.content}]})

            payload = {
                "contents": contents,
                "generationConfig": {
                    "maxOutputTokens": kwargs.get("max_tokens", 4096),
                    "temperature": kwargs.get("temperature", 0.7),
                },
            }

            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/models/{model}:streamGenerateContent?key={api_key}",
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=60.0,
                ) as response:
                    if response.status_code != 200:
                        raise Exception(f"Stream error: {response.status_code}")

                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                candidate = data["candidates"][0]
                                for part in candidate["content"].get("parts", []):
                                    if "text" in part:
                                        yield part["text"]
                            except json.JSONDecodeError:
                                continue

        except Exception as e:
            logger.error(f"Google Gemini stream error: {e}")
            raise
