from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

class OpenRouterProvider:
    ""

    def __init__(self, api_key: str = "", model: str = "") -> None:
        self.api_key = api_key
        self.model = model or "anthropic/claude-3.5-sonnet"
        self._client = None

    async def complete(
        self,
        messages: list[dict],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> str:
        ""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
"HTTP-Referer": "https://github.com/AnishtayiN/Bahram-Agent",
                    "X-Title": "Bahram Agent",
                    },
                    json={
                        "model": model or self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    timeout=120.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    error = response.json().get("error", {}).get("message", "Unknown error")
                    raise RuntimeError(f"OpenRouter API error: {error}")

        except ImportError:
            raise ImportError("httpx not installed. Run: pip install httpx")
        except Exception as e:
            logger.error(f"OpenRouter completion failed: {e}")
            raise

    async def stream(
        self,
        messages: list[dict],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        ""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
"HTTP-Referer": "https://github.com/AnishtayiN/Bahram-Agent",
                    "X-Title": "Bahram Agent",
                    },
                    json={
                        "model": model or self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": True,
                    },
                    timeout=120.0,
                ) as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                import json
                                chunk = json.loads(data)
                                delta = chunk["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                            except Exception:
                                pass

        except ImportError:
            raise ImportError("httpx not installed. Run: pip install httpx")

    def get_models(self) -> list[str]:
        ""
        return [
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "google/gemini-pro",
            "meta-llama/llama-3.1-405b-instruct",
            "mistralai/mixtral-8x7b-instruct",
        ]

    def get_provider_info(self) -> dict[str, Any]:
        ""
        return {
            "name": "openrouter",
            "configured": bool(self.api_key),
            "model": self.model,
        }
