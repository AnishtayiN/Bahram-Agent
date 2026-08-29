from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

class OllamaProvider:
    ""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model or "llama3"

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
                    f"{self.base_url}/api/chat",
                    json={
                        "model": model or self.model,
                        "messages": messages,
                        "stream": False,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens,
                        },
                    },
                    timeout=120.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("message", {}).get("content", "")
                else:
                    error = response.text
                    raise RuntimeError(f"Ollama API error: {error}")

        except ImportError:
            raise ImportError("httpx not installed. Run: pip install httpx")
        except Exception as e:
            logger.error(f"Ollama completion failed: {e}")
            raise

    async def list_models(self) -> list[str]:
        ""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/tags", timeout=10.0)

                if response.status_code == 200:
                    data = response.json()
                    return [m["name"] for m in data.get("models", [])]
                return []

        except Exception:
            return []

    def get_provider_info(self) -> dict[str, Any]:
        ""
        return {
            "name": "ollama",
            "base_url": self.base_url,
            "model": self.model,
        }
