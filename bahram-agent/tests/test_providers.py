from __future__ import annotations

from bahram.core.engine import Message, MessageRole
from bahram.providers.anthropic import AnthropicProvider
from bahram.providers.compat import OpenAICompatibleProvider
from bahram.providers.deepseek import DeepSeekProvider
from bahram.providers.google import GoogleProvider
from bahram.providers.groq import GroqProvider
from bahram.providers.mistral import MistralProvider
from bahram.providers.ollama import OllamaProvider
from bahram.providers.openai import OpenAIProvider
from bahram.providers.openrouter import OpenRouterProvider


class TestBaseProvider:
    def test_prepare_messages(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o")
        messages = [
            Message(role=MessageRole.SYSTEM, content="You are helpful."),
            Message(role=MessageRole.USER, content="Hello"),
            Message(role=MessageRole.ASSISTANT, content="Hi there!"),
        ]
        raw, system = provider._prepare_messages(messages)
        assert system == "You are helpful."
        assert len(raw) == 2
        assert raw[0]["role"] == "user"
        assert raw[1]["role"] == "assistant"

    def test_prepare_tools(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o")
        tools = [
            {
                "name": "bash",
                "description": "Run bash",
                "parameters": {"type": "object", "properties": {}},
            }
        ]
        result = provider._prepare_tools(tools)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "bash"

    def test_parse_openai_response(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o")
        data = {
            "choices": [
                {
                    "message": {
                        "content": "Hello!",
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "function": {"name": "bash", "arguments": '{"command": "ls"}'},
                            }
                        ],
                    }
                }
            ]
        }
        response = provider._parse_openai_response(data)
        assert response.content == "Hello!"
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "bash"

    def test_get_model(self):
        provider = OpenAIProvider(api_key="test", model="gpt-4o")
        assert provider._get_model(None) == "gpt-4o"
        assert provider._get_model("gpt-4o-mini") == "gpt-4o-mini"


class TestOpenAIProvider:
    def test_init(self):
        p = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        assert p.api_key == "sk-test"
        assert p.model == "gpt-4o"

    def test_get_models(self):
        p = OpenAIProvider(api_key="test")
        models = p.get_models()
        assert "gpt-4o" in models

    def test_provider_info(self):
        p = OpenAIProvider(api_key="test")
        info = p.get_provider_info()
        assert info["name"] == "openai"
        assert info["configured"] is True


class TestAnthropicProvider:
    def test_init(self):
        p = AnthropicProvider(api_key="test-key")
        assert p.model == "claude-sonnet-4-20250514"

    def test_convert_messages(self):
        p = AnthropicProvider(api_key="test")
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        result = p._convert_messages(messages)
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"

    def test_convert_tools(self):
        p = AnthropicProvider(api_key="test")
        tools = [
            {
                "type": "function",
                "function": {"name": "bash", "description": "Run", "parameters": {}},
            }
        ]
        result = p._convert_tools(tools)
        assert result[0]["name"] == "bash"
        assert "input_schema" in result[0]

    def test_parse_anthropic_response(self):
        p = AnthropicProvider(api_key="test")
        data = {
            "content": [
                {"type": "text", "text": "Hello"},
                {"type": "tool_use", "id": "123", "name": "bash", "input": {"command": "ls"}},
            ]
        }
        response = p._parse_anthropic_response(data)
        assert "Hello" in response.content
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "bash"


class TestGroqProvider:
    def test_init(self):
        p = GroqProvider(api_key="test")
        assert p.model == "llama3-8b-8192"

    def test_get_models(self):
        p = GroqProvider(api_key="test")
        assert "llama3-8b-8192" in p.get_models()


class TestDeepSeekProvider:
    def test_init(self):
        p = DeepSeekProvider(api_key="test")
        assert p.model == "deepseek-chat"

    def test_base_url(self):
        p = DeepSeekProvider(api_key="test")
        assert "deepseek" in p.base_url


class TestMistralProvider:
    def test_init(self):
        p = MistralProvider(api_key="test")
        assert p.model == "mistral-large-latest"


class TestOpenRouterProvider:
    def test_init(self):
        p = OpenRouterProvider(api_key="test")
        assert "openrouter" in p.base_url


class TestOllamaProvider:
    def test_init(self):
        p = OllamaProvider()
        assert p.model == "llama3"
        assert "localhost" in p.base_url

    def test_get_models(self):
        p = OllamaProvider()
        assert "llama3" in p.get_models()


class TestGoogleProvider:
    def test_init(self):
        p = GoogleProvider(api_key="test")
        assert p.model == "gemini-1.5-flash"


class TestOpenAICompatibleProvider:
    def test_init(self):
        p = OpenAICompatibleProvider(
            api_key="test", model="test-model", base_url="http://localhost:8000"
        )
        assert p.api_key == "test"
        assert p.model == "test-model"
        assert p.base_url == "http://localhost:8000"
