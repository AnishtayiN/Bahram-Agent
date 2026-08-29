"""LLM providers for Bahram Agent."""

from bahram.providers.base import BaseProvider
from bahram.providers.anthropic import AnthropicProvider
from bahram.providers.openai import OpenAIProvider
from bahram.providers.openrouter import OpenRouterProvider

__all__ = ["BaseProvider", "AnthropicProvider", "OpenAIProvider", "OpenRouterProvider"]


async def init_providers(engine: "AgentEngine", config: "Config") -> None:
    """Initialize all configured providers."""
    for provider_name, provider_config in config.providers.items():
        try:
            if provider_name == "anthropic":
                provider = AnthropicProvider(provider_config)
            elif provider_name == "openai":
                provider = OpenAIProvider(provider_config)
            elif provider_name == "openrouter":
                provider = OpenRouterProvider(provider_config)
            else:
                logger.warning(f"Unknown provider: {provider_name}")
                continue

            engine.register_provider(provider_name, provider)
        except Exception as e:
            logger.error(f"Failed to initialize provider {provider_name}: {e}")
