"""Tests for providers."""
import pytest
from bahram.providers.groq import GroqProvider
from bahram.providers.openrouter import OpenRouterProvider
from bahram.providers.ollama import OllamaProvider

class TestGroqProvider:
    def test_provider_creation(self):
        provider = GroqProvider(api_key="test")
        assert provider is not None

    def test_get_models(self):
        provider = GroqProvider(api_key="test")
        models = provider.get_models()
        assert len(models) > 0

    def test_provider_info(self):
        provider = GroqProvider(api_key="test")
        info = provider.get_provider_info()
        assert info["name"] == "groq"

class TestOpenRouterProvider:
    def test_provider_creation(self):
        provider = OpenRouterProvider(api_key="test")
        assert provider is not None

    def test_get_models(self):
        provider = OpenRouterProvider(api_key="test")
        models = provider.get_models()
        assert len(models) > 0

class TestOllamaProvider:
    def test_provider_creation(self):
        provider = OllamaProvider(base_url="http://localhost:11434")
        assert provider is not None

    def test_provider_info(self):
        provider = OllamaProvider()
        info = provider.get_provider_info()
        assert info["name"] == "ollama"
