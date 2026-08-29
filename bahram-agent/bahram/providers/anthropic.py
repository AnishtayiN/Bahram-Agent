"""Anthropic Claude LLM provider for Bahram Agent."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AnthropicProvider:
    """Anthropic Claude LLM provider."""

    def __init__(self, api_key: str = "", model: str = "") -> None:
        self.api_key = api_key
        self.model = model or "claude-3-5-sonnet-20241022"

    async def complete(
        self,
        messages: list[dict],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
        system: str = "",
    ) -> str:
        """Complete a conversation."""
        try:
            import httpx

            # Separate system message
            if not system and messages and messages[0].get("role") == "system":
                system = messages[0]["content"]
                messages = messages[1:]

            async with httpx.AsyncClient() as client:
                payload = {
                    "model": model or self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if system:
                    payload["system"] = system

                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=120.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["content"][0]["text"]
                else:
                    error = response.json().get("error", {}).get("message", "Unknown error")
                    raise RuntimeError(f"Anthropic API error: {error}")

        except ImportError:
            raise ImportError("httpx not installed. Run: pip install httpx")
        except Exception as e:
            logger.error(f"Anthropic completion failed: {e}")
            raise

    def get_models(self) -> list[str]:
        """Get available models."""
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-haiku-20240307",
        ]

    def get_provider_info(self) -> dict[str, Any]:
        """Get provider information."""
        return {
            "name": "anthropic",
            "configured": bool(self.api_key),
            "model": self.model,
        }
