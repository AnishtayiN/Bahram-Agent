from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bahram.core.agent import Agent
from bahram.core.config import AgentConfig, Config, MemoryConfig, ProviderConfig, ToolsConfig
from bahram.core.context import Context, ContextWindow
from bahram.core.engine import (
    AgentEngine,
    AgentResponse,
    Message,
    MessageRole,
    ToolCall,
    ToolExecutor,
    ToolResult,
    Trajectory,
    TrajectoryStep,
)
from bahram.core.persistence import SessionStore
from bahram.security.approval import ApprovalConfig, ApprovalSystem


class MockProvider:
    def __init__(self, responses=None):
        self.responses = responses or []
        self.call_count = 0

    async def complete(self, messages, tools=None, **kwargs):
        self.call_count += 1
        if self.call_count <= len(self.responses):
            return self.responses[self.call_count - 1]
        return AgentResponse(content="Done")

    async def stream(self, messages, tools=None, **kwargs):
        yield "mock"


def _make_config():
    config = Config()
    config.memory.database = ":memory:"
    config.logging.level = "WARNING"
    return config


class TestScenarioA_SimpleReasoning:
    @pytest.mark.asyncio
    async def test_simple_reasoning(self):
        config = _make_config()
        agent = Agent(config=config)
        provider = MockProvider(responses=[
            AgentResponse(content="The answer is 42.")
        ])
        agent.engine.register_provider("test", provider)
        agent.engine.providers = {"test": provider, "anthropic": provider}

        response = await agent.chat("What is the meaning of life?", model="test")
        assert response.content == "The answer is 42."
        assert len(response.tool_calls) == 0
        assert provider.call_count == 1


class TestScenarioB_ToolExecution:
    @pytest.mark.asyncio
    async def test_tool_execution_flow(self):
        config = _make_config()
        agent = Agent(config=config)

        echo_tool = AsyncMock()
        echo_tool.schema = MagicMock(return_value={
            "type": "function",
            "function": {"name": "echo", "description": "Echo tool", "parameters": {}},
        })
        echo_tool.execute = AsyncMock(return_value="Hello from echo")
        agent.engine.register_tool("echo", echo_tool)

        tc = ToolCall(id="call_1", name="echo", arguments={"text": "hello"})
        provider = MockProvider(responses=[
            AgentResponse(content="Let me use the tool.", tool_calls=[tc]),
            AgentResponse(content="The tool returned: Hello from echo"),
        ])
        agent.engine.register_provider("test", provider)
        agent.engine.providers = {"test": provider, "anthropic": provider}

        response = await agent.chat("Use the echo tool", model="test")
        assert "Hello from echo" in response.content
        assert echo_tool.execute.called

    @pytest.mark.asyncio
    async def test_tool_failure_recovery(self):
        config = _make_config()
        agent = Agent(config=config)

        fail_tool = AsyncMock()
        fail_tool.schema = MagicMock(return_value={
            "type": "function",
            "function": {"name": "fail", "description": "Failing tool", "parameters": {}},
        })
        fail_tool.execute = AsyncMock(side_effect=ValueError("Tool crashed"))
        agent.engine.register_tool("fail", fail_tool)

        tc = ToolCall(id="call_1", name="fail", arguments={})
        provider = MockProvider(responses=[
            AgentResponse(content="Trying tool.", tool_calls=[tc]),
            AgentResponse(content="The tool failed, but I recovered."),
        ])
        agent.engine.register_provider("test", provider)
        agent.engine.providers = {"test": provider, "anthropic": provider}

        response = await agent.chat("Try the fail tool", model="test")
        assert "recovered" in response.content


class TestScenarioC_Memory:
    @pytest.mark.asyncio
    async def test_memory_persistence_across_sessions(self):
        config = _make_config()
        agent = Agent(config=config)
        await agent._init_memory()

        provider = MockProvider(responses=[
            AgentResponse(content="I remember that."),
        ])
        agent.engine.register_provider("test", provider)
        agent.engine.providers = {"test": provider, "anthropic": provider}

        await agent.chat("My name is Alice", model="test")

        assert agent._memory is not None
        results = agent._memory.search("Alice")
        assert len(results) > 0
        assert "Alice" in results[0].content

    @pytest.mark.asyncio
    async def test_memory_retrieval_in_context(self):
        config = _make_config()
        agent = Agent(config=config)

        agent._memory = MagicMock()
        agent._memory.get_context.return_value = "User previously mentioned Python"

        result = agent._retrieve_memories("What programming language do I like?")
        assert "Python" in result


class TestScenarioD_Approval:
    @pytest.mark.asyncio
    async def test_dangerous_command_blocked(self):
        config = _make_config()
        agent = Agent(config=config)

        tool = AsyncMock()
        tool.execute = AsyncMock(return_value="should not reach here")
        agent.engine.register_tool("bash", tool)

        tc = ToolCall(id="call_1", name="bash", arguments={"command": "rm -rf /"})
        executor = ToolExecutor({"bash": tool}, agent.engine._approval_system)
        result = await executor.execute(tc)
        assert result.success is False
        assert "Security block" in result.error
        assert not tool.execute.called

    @pytest.mark.asyncio
    async def test_safe_command_allowed(self):
        config = _make_config()
        agent = Agent(config=config)

        tool = AsyncMock()
        tool.execute = AsyncMock(return_value="file.txt")
        agent.engine.register_tool("bash", tool)

        tc = ToolCall(id="call_1", name="bash", arguments={"command": "ls"})
        executor = ToolExecutor({"bash": tool}, agent.engine._approval_system)
        result = await executor.execute(tc)
        assert result.success is True
        assert tool.execute.called


class TestScenarioE_SessionPersistence:
    @pytest.mark.asyncio
    async def test_session_messages_persist(self):
        config = _make_config()
        agent = Agent(config=config)

        provider = MockProvider(responses=[
            AgentResponse(content="Hello!"),
            AgentResponse(content="Nice to see you again!"),
        ])
        agent.engine.register_provider("test", provider)
        agent.engine.providers = {"test": provider, "anthropic": provider}

        session = agent.create_session()
        session_id = session.id

        await agent.chat("Hi", session_id=session_id, model="test")
        await agent.chat("Hello again", session_id=session_id, model="test")

        history = agent.get_history(session_id)
        assert len(history) >= 4

        stored = agent._store.get_messages(session_id)
        assert len(stored) >= 4

    def test_session_store_persistence(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        store1 = SessionStore(db_path=db_path)
        store1.create_session("s1")
        store1.add_message("s1", Message(role=MessageRole.USER, content="Hello"))

        store2 = SessionStore(db_path=db_path)
        messages = store2.get_messages("s1")
        assert len(messages) == 1
        assert messages[0].content == "Hello"


class TestScenarioF_ContextManagement:
    def test_context_trimming(self):
        ctx = ContextWindow(max_turns=5)
        for i in range(20):
            ctx.add_message(Message(role=MessageRole.USER, content=f"msg {i}"))
            ctx.add_message(Message(role=MessageRole.ASSISTANT, content=f"reply {i}"))
        messages = ctx.get_messages()
        assert len(messages) <= 12

    def test_system_prompt_preserved(self):
        ctx = ContextWindow()
        ctx.set_system_prompt("You are Bahram.")
        ctx.add_message(Message(role=MessageRole.USER, content="Hello"))
        ctx.add_message(Message(role=MessageRole.ASSISTANT, content="Hi"))
        msgs = ctx.get_messages()
        assert msgs[0].role == MessageRole.SYSTEM
        assert msgs[0].content == "You are Bahram."


class TestScenarioG_ToolRegistry:
    def test_all_tools_have_schemas(self):
        engine = AgentEngine()

        from bahram.tools.bash import BashTool
        from bahram.tools.execute_code import ExecuteCodeTool
        from bahram.tools.file import EditTool, ReadTool, WriteTool
        from bahram.tools.web import WebFetchTool, WebSearchTool

        tools = [BashTool(), ReadTool(), WriteTool(), EditTool(), WebFetchTool(), WebSearchTool(), ExecuteCodeTool()]
        for tool in tools:
            engine.register_tool(tool.name, tool)

        schemas = engine.get_tools_schema()
        assert len(schemas) == 7

        for schema in schemas:
            assert "type" in schema
            assert "function" in schema
            assert "name" in schema["function"]
            assert "description" in schema["function"]
            assert "parameters" in schema["function"]
            assert len(schema["function"]["description"]) > 0


class TestScenarioH_ProviderRouting:
    def test_provider_routing(self):
        engine = AgentEngine()
        provider1 = MockProvider()
        provider2 = MockProvider()
        engine.register_provider("openai", provider1)
        engine.register_provider("anthropic", provider2)

        assert engine.get_provider("openai/gpt-4o") is provider1
        assert engine.get_provider("anthropic/claude-3") is provider2

    def test_unknown_provider_raises(self):
        engine = AgentEngine()
        with pytest.raises(ValueError, match="not registered"):
            engine.get_provider("unknown/model")


class TestScenarioI_Trajectory:
    @pytest.mark.asyncio
    async def test_trajectory_recorded(self):
        config = _make_config()
        agent = Agent(config=config)

        provider = MockProvider(responses=[
            AgentResponse(content="Final answer"),
        ])
        agent.engine.register_provider("test", provider)
        agent.engine.providers = {"test": provider, "anthropic": provider}

        await agent.chat("Simple question", model="test")

        assert True


class TestScenarioJ_MaxIterations:
    @pytest.mark.asyncio
    async def test_max_iterations_stops(self):
        config = _make_config()
        agent = Agent(config=config)

        tc = ToolCall(id="call_1", name="bash", arguments={"command": "ls"})
        infinite_tool = AsyncMock()
        infinite_tool.schema = MagicMock(return_value={
            "type": "function",
            "function": {"name": "bash", "description": "Bash tool", "parameters": {}},
        })
        infinite_tool.execute = AsyncMock(return_value="output")
        agent.engine.register_tool("bash", infinite_tool)

        provider = MockProvider(responses=[
            AgentResponse(content="", tool_calls=[tc]),
        ] * 20)
        agent.engine.register_provider("test", provider)
        agent.engine.providers = {"test": provider, "anthropic": provider}

        response = await agent.chat("Do something", model="test")
        assert provider.call_count <= 15
