from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

class GoogleProvider:
    ""

    def __init__(self, api_key: str = "", model: str = "") -> None:
        self.api_key = api_key
        self.model = model or "gemini-pro"

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

            contents = []
            for msg in messages:
                role = "user" if msg["role"] in ("user", "system") else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}],
                })

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model or self.model}:generateContent?key={self.api_key}",
                    headers={
                        "Content-Type": "application/json",
                    },
                    json={
                        "contents": contents,
                        "generationConfig": {
                            "temperature": temperature,
                            "maxOutputTokens": max_tokens,
                        },
                    },
                    timeout=120.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    error = response.json().get("error", {}).get("message", "Unknown error")
                    raise RuntimeError(f"Google API error: {error}")

        except ImportError:
            raise ImportError("httpx not installed. Run: pip install httpx")
        except Exception as e:
            logger.error(f"Google completion failed: {e}")
            raise

    def get_models(self) -> list[str]:
        ""
        return [
            "gemini-pro",
            "gemini-pro-vision",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ]

    def get_provider_info(self) -> dict[str, Any]:
        ""
        return {
            "name": "google",
            "configured": bool(self.api_key),
            "model": self.model,
        }
