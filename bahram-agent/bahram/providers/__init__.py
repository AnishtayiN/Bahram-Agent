"""LLM provider registry.

Public objects: ``init_providers`` - builds the provider map from the API keys
that are actually present in the environment or configuration.
"""

from __future__ import annotations

import logging
from typing import Any

from bahram.providers.anthropic import AnthropicProvider
from bahram.providers.base import BaseProvider
from bahram.providers.custom import CustomProvider
from bahram.providers.deepseek import DeepSeekProvider
from bahram.providers.google import GoogleProvider
from bahram.providers.groq import GroqProvider
from bahram.providers.huggingface import HuggingFaceProvider
from bahram.providers.kimi import KimiProvider
from bahram.providers.lmstudio import LMStudioProvider
from bahram.providers.minimax import MiniMaxProvider
from bahram.providers.mistral import MistralProvider
from bahram.providers.nous import NousProvider
from bahram.providers.nvidia import NvidiaProvider
from bahram.providers.ollama import OllamaProvider
from bahram.providers.openai import OpenAIProvider
from bahram.providers.openrouter import OpenRouterProvider
from bahram.providers.xiaomi import XiaomiProvider
from bahram.providers.zhipu import ZhipuProvider

__all__ = [
    "BaseProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "GroqProvider",
    "DeepSeekProvider",
    "MistralProvider",
    "OpenRouterProvider",
    "NousProvider",
    "NvidiaProvider",
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

logger = logging.getLogger(__name__)

PROVIDER_MAP: dict[str, type[BaseProvider]] = {
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


async def init_providers(engine: Any, config: Any) -> None:
    """
    Initialise providers.

    Args:
        engine (Any): engine.
        config (Any): configuration object.

    Note:
        Coroutine - must be awaited.
    """
    for provider_name, provider_config in config.providers.items():
        try:
            provider_class = PROVIDER_MAP.get(provider_name)
            if provider_class is None:
                logger.warning(f"Unknown provider: {provider_name}")
                continue
            kwargs: dict[str, Any] = {
                "api_key": provider_config.api_key,
                "model": provider_config.models[0] if provider_config.models else "",
            }
            if provider_config.base_url:
                kwargs["base_url"] = provider_config.base_url
            if provider_config.temperature:
                kwargs["temperature"] = provider_config.temperature
            if provider_config.max_tokens:
                kwargs["max_tokens"] = provider_config.max_tokens
            provider = provider_class(**kwargs)
            engine.register_provider(provider_name, provider)
            logger.info(f"Registered provider: {provider_name}")
        except Exception as e:
            logger.error(f"Failed to initialize provider {provider_name}: {e}")
