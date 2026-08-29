from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

class MistralProvider:
    ""

    def __init__(self, api_key: str = "", model: str = "") -> None:
        self.api_key = api_key
        self.model = model or "mistral-large-latest"

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
                    "https://api.mistral.ai/v1/chat/completions",
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
                    timeout=120.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    error = response.json().get("error", {}).get("message", "Unknown error")
                    raise RuntimeError(f"Mistral API error: {error}")

        except ImportError:
            raise ImportError("httpx not installed. Run: pip install httpx")
        except Exception as e:
            logger.error(f"Mistral completion failed: {e}")
            raise

    def get_models(self) -> list[str]:
        ""
        return [
            "mistral-large-latest",
            "mistral-medium-latest",
            "mistral-small-latest",
            "open-mixtral-8x7b",
            "open-mixtral-8x22b",
        ]

    def get_provider_info(self) -> dict[str, Any]:
        ""
        return {
            "name": "mistral",
            "configured": bool(self.api_key),
            "model": self.model,
        }
