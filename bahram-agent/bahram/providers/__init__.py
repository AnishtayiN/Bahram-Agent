"""LLM providers for Bahram Agent."""

from bahram.providers.base import BaseProvider
from bahram.providers.anthropic import AnthropicProvider
from bahram.providers.openai import OpenAIProvider
from bahram.providers.openrouter import OpenRouterProvider
from bahram.providers.nous import NousProvider
from bahram.providers.nvidia import NvidiaProvider
from bahram.providers.groq import GroqProvider
from bahram.providers.deepseek import DeepSeekProvider
from bahram.providers.mistral import MistralProvider
from bahram.providers.google import GoogleProvider
from bahram.providers.huggingface import HuggingFaceProvider
from bahram.providers.xiaomi import XiaomiProvider
from bahram.providers.minimax import MiniMaxProvider
from bahram.providers.kimi import KimiProvider
from bahram.providers.zhipu import ZhipuProvider
from bahram.providers.ollama import OllamaProvider
from bahram.providers.lmstudio import LMStudioProvider
from bahram.providers.custom import CustomProvider

__all__ = [
    "BaseProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
    "NousProvider",
    "NvidiaProvider",
    "GroqProvider",
    "DeepSeekProvider",
    "MistralProvider",
    "GoogleProvider",
    "HuggingFaceProvider",
    "XiaomiProvider",
    "MiniMaxProvider",
    "KimiProvider",
    "ZhipuProvider",
    "OllamaProvider",
    "LMStudioProvider",
    "CustomProvider",
]

import logging

logger = logging.getLogger(__name__)


async def init_providers(engine: "AgentEngine", config: "Config") -> None:
    """Initialize all configured providers."""
    provider_map = {
        "anthropic": AnthropicProvider,
        "openai": OpenAIProvider,
        "openrouter": OpenRouterProvider,
        "nous": NousProvider,
        "nvidia": NvidiaProvider,
        "groq": GroqProvider,
        "deepseek": DeepSeekProvider,
        "mistral": MistralProvider,
        "google": GoogleProvider,
        "huggingface": HuggingFaceProvider,
        "xiaomi": XiaomiProvider,
        "minimax": MiniMaxProvider,
        "kimi": KimiProvider,
        "zhipu": ZhipuProvider,
        "ollama": OllamaProvider,
        "lmstudio": LMStudioProvider,
        "custom": CustomProvider,
    }

    for provider_name, provider_config in config.providers.items():
        try:
            provider_class = provider_map.get(provider_name)
            if provider_class:
                provider = provider_class(provider_config)
                engine.register_provider(provider_name, provider)
                logger.info(f"Registered provider: {provider_name}")
            else:
                logger.warning(f"Unknown provider: {provider_name}")
        except Exception as e:
            logger.error(f"Failed to initialize provider {provider_name}: {e}")
