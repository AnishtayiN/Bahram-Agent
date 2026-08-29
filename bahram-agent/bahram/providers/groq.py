from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

class GroqProvider:
    ""

    def __init__(self, api_key: str = "", model: str = "") -> None:
        self.api_key = api_key
        self.model = model or "llama3-8b-8192"
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
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model or self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    timeout=60.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    error = response.json().get("error", {}).get("message", "Unknown error")
                    raise RuntimeError(f"Groq API error: {error}")

        except ImportError:
            raise ImportError("httpx not installed. Run: pip install httpx")
        except Exception as e:
            logger.error(f"Groq completion failed: {e}")
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
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model or self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": True,
                    },
                    timeout=60.0,
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
            "llama3-8b-8192",
            "llama3-70b-8192",
            "mixtral-8x7b-32768",
            "gemma-7b-it",
        ]

    def get_provider_info(self) -> dict[str, Any]:
        ""
        return {
            "name": "groq",
            "configured": bool(self.api_key),
            "model": self.model,
        }
