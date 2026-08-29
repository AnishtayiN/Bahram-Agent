"""Hugging Face LLM provider for Bahram Agent."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HuggingFaceProvider:
    """Hugging Face LLM provider."""

    def __init__(self, api_key: str = "", model: str = "") -> None:
        self.api_key = api_key
        self.model = model or "meta-llama/Meta-Llama-3.1-8B-Instruct"

    async def complete(
        self,
        messages: list[dict],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> str:
        """Complete a conversation."""
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api-inference.huggingface.co/models/{model or self.model}",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "inputs": messages[-1]["content"],
                        "parameters": {
                            "temperature": temperature,
                            "max_new_tokens": max_tokens,
                        },
                    },
                    timeout=120.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and len(data) > 0:
                        return data[0].get("generated_text", "")
                    return str(data)
                else:
                    error = response.json().get("error", "Unknown error")
                    raise RuntimeError(f"HuggingFace API error: {error}")

        except ImportError:
            raise ImportError("httpx not installed. Run: pip install httpx")
        except Exception as e:
            logger.error(f"HuggingFace completion failed: {e}")
            raise

    def get_models(self) -> list[str]:
        """Get available models."""
        return [
            "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "meta-llama/Meta-Llama-3.1-70B-Instruct",
            "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "google/gemma-2-9b-it",
        ]

    def get_provider_info(self) -> dict[str, Any]:
        """Get provider information."""
        return {
            "name": "huggingface",
            "configured": bool(self.api_key),
            "model": self.model,
        }
