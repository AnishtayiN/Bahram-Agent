from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from bahram.core.agent import Agent
from bahram.core.config import (
    Config,
)
from bahram.core.engine import AgentResponse, ToolCall


class MockProvider:
    def __init__(self, response_text="Mock response", tool_calls=None):
        self.response_text = response_text
        self.tool_calls = tool_calls or []
        self.call_count = 0

    async def complete(self, messages, tools=None, **kwargs):
        self.call_count += 1
        if self.call_count > 1:
            return AgentResponse(content=self.response_text, tool_calls=[])
        return AgentResponse(content=self.response_text, tool_calls=self.tool_calls)

    async def stream(self, messages, tools=None, **kwargs):
        yield self.response_text


def _make_config():
    config = Config()
    config.memory.database = ":memory:"
    config.logging.level = "WARNING"
    return config


class TestAgentInit:
    def test_init_with_config(self):
        config = _make_config()
        agent = Agent(config=config)
        assert agent.config is config

    def test_default_config(self):
        config = _make_config()
        agent = Agent(config=config)
        assert agent.config.agent.name == "Bahram"


class TestAgentSession:
    def test_create_session(self):
        config = _make_config()
        agent = Agent(config=config)
        session = agent.create_session()
        assert session.id in agent.sessions

    def test_get_session(self):
        config = _make_config()
        agent = Agent(config=config)
        session = agent.create_session()
        retrieved = agent.get_session(session.id)
        assert retrieved is not None

    def test_delete_session(self):
        config = _make_config()
        agent = Agent(config=config)
        session = agent.create_session()
        agent.delete_session(session.id)
        assert agent.get_session(session.id) is None


class TestAgentChat:
    @pytest.mark.asyncio
    async def test_chat_no_tools(self):
        config = _make_config()
        agent = Agent(config=config)
        mock_provider = MockProvider(response_text="Hello!")
        agent.engine.register_provider("test", mock_provider)
        agent.engine.providers = {"test": mock_provider, "anthropic": mock_provider}

        response = await agent.chat("Hi", model="test")
        assert response.content == "Hello!"
        assert mock_provider.call_count == 1

    @pytest.mark.asyncio
    async def test_chat_with_tool_calls(self):
        config = _make_config()
        agent = Agent(config=config)
        tool = AsyncMock()
        tool.schema = MagicMock(
            return_value={
                "type": "function",
                "function": {"name": "echo", "description": "Echo tool", "parameters": {}},
            }
        )
        tool.execute = AsyncMock(return_value="Tool output")
        agent.engine.register_tool("echo", tool)

        tc = ToolCall(id="1", name="echo", arguments={"text": "hello"})
        mock_provider = MockProvider(response_text="Done", tool_calls=[tc])
        agent.engine.register_provider("test", mock_provider)
        agent.engine.providers = {"test": mock_provider, "anthropic": mock_provider}

        response = await agent.chat("Use echo tool", model="test")
        assert response.content == "Done"

    @pytest.mark.asyncio
    async def test_chat_creates_session(self):
        config = _make_config()
        agent = Agent(config=config)
        mock_provider = MockProvider()
        agent.engine.register_provider("test", mock_provider)
        agent.engine.providers = {"test": mock_provider, "anthropic": mock_provider}

        await agent.chat("Hi", model="test")
        assert len(agent.sessions) == 1


class TestAgentMemory:
    def test_memory_retrieval(self):
        config = _make_config()
        agent = Agent(config=config)
        agent._memory = MagicMock()
        agent._memory.get_context.return_value = "Python is great"
        result = agent._retrieve_memories("Tell me about Python")
        assert "Python" in result

    def test_memory_storage(self):
        config = _make_config()
        agent = Agent(config=config)
        agent._memory = MagicMock()
        agent._store_memory("question", "answer")
        agent._memory.add.assert_called_once()


class TestAgentSkills:
    async def test_skills_retrieval(self):
        config = _make_config()
        agent = Agent(config=config)
        agent._skills = MagicMock()
        mock_skill = MagicMock()
        mock_skill.metadata.name = "test_skill"
        mock_skill.metadata.description = "A test skill"
        # SkillManager.find_skill is a coroutine, so the double must be too.
        agent._skills.find_skill = AsyncMock(return_value=mock_skill)
        result = await agent._retrieve_skills("do something")
        assert "test_skill" in result

    async def test_no_skills(self):
        config = _make_config()
        agent = Agent(config=config)
        result = await agent._retrieve_skills("do something")
        assert result == ""


class TestAgentSystemPrompt:
    def test_default_prompt(self):
        config = _make_config()
        agent = Agent(config=config)
        prompt = agent._build_system_prompt()
        assert "Bahram" in prompt

    def test_prompt_includes_tools(self):
        config = _make_config()
        agent = Agent(config=config)
        tool = MagicMock()
        tool.description = "A test tool"
        agent.engine.register_tool("test_tool", tool)
        prompt = agent._build_system_prompt()
        assert "test_tool" in prompt
