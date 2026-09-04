from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from bahram.core.config import Config
from bahram.core.engine import (
    AgentEngine,
    Message,
    MessageRole,
    ToolCall,
    ToolExecutor,
    ToolResult,
)


class TestMessage:
    def test_create_message(self):
        msg = Message(role=MessageRole.USER, content="hello")
        assert msg.role == MessageRole.USER
        assert msg.content == "hello"
        assert msg.timestamp > 0

    def test_message_roles(self):
        for role in MessageRole:
            msg = Message(role=role, content="test")
            assert msg.role == role


class TestToolCall:
    def test_create_tool_call(self):
        tc = ToolCall(id="1", name="bash", arguments={"command": "ls"})
        assert tc.id == "1"
        assert tc.name == "bash"
        assert tc.arguments["command"] == "ls"


class TestToolResult:
    def test_success_result(self):
        r = ToolResult(tool_call_id="1", content="output", success=True)
        assert r.success is True
        assert r.content == "output"

    def test_error_result(self):
        r = ToolResult(tool_call_id="1", content="", success=False, error="fail")
        assert r.success is False
        assert r.error == "fail"


class TestSecurityPolicy:
    def test_approval_system_safe(self):
        from bahram.security.approval import ApprovalSystem
        system = ApprovalSystem()
        is_dangerous, reason = system.check_command("ls -la")
        assert is_dangerous is False

    def test_approval_system_dangerous(self):
        from bahram.security.approval import ApprovalSystem
        system = ApprovalSystem()
        is_dangerous, reason = system.check_command("rm -rf /")
        assert is_dangerous is True

    @pytest.mark.asyncio
    async def test_engine_blocks_dangerous(self):
        engine = AgentEngine()
        executor = ToolExecutor({}, engine._approval_system)
        tc = ToolCall(id="1", name="bash", arguments={"command": "rm -rf /"})
        result = await executor.execute(tc)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_engine_allows_safe(self):
        engine = AgentEngine()
        tool = AsyncMock()
        tool.execute = AsyncMock(return_value="output")
        executor = ToolExecutor({"bash": tool}, engine._approval_system)
        tc = ToolCall(id="1", name="bash", arguments={"command": "ls"})
        result = await executor.execute(tc)
        assert result.success is True


class TestAgentEngine:
    def test_register_tool(self):
        engine = AgentEngine()
        tool = MagicMock()
        tool.schema.return_value = {"type": "function", "function": {"name": "test", "description": "test tool", "parameters": {}}}
        engine.register_tool("test", tool)
        assert "test" in engine.tools

    def test_get_tools_schema(self):
        engine = AgentEngine()
        tool = MagicMock()
        tool.schema.return_value = {"type": "function", "function": {"name": "test", "description": "test", "parameters": {}}}
        engine.register_tool("test", tool)
        schemas = engine.get_tools_schema()
        assert len(schemas) == 1

    @pytest.mark.asyncio
    async def test_security_blocks_dangerous(self):
        engine = AgentEngine()
        executor = ToolExecutor({}, engine._approval_system)
        tc = ToolCall(id="1", name="bash", arguments={"command": "rm -rf /"})
        result = await executor.execute(tc)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_unknown_tool(self):
        engine = AgentEngine()
        executor = ToolExecutor({}, engine._approval_system)
        tc = ToolCall(id="1", name="nonexistent", arguments={})
        result = await executor.execute(tc)
        assert result.success is False
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        engine = AgentEngine()
        tool = AsyncMock()
        tool.execute = AsyncMock(return_value="success output")
        executor = ToolExecutor({"echo": tool}, engine._approval_system)
        tc = ToolCall(id="1", name="echo", arguments={"text": "hello"})
        result = await executor.execute(tc)
        assert result.success is True
        assert "success output" in result.content

    @pytest.mark.asyncio
    async def test_execute_tool_error(self):
        engine = AgentEngine()
        tool = AsyncMock()
        tool.execute = AsyncMock(side_effect=ValueError("bad args"))
        executor = ToolExecutor({"fail": tool}, engine._approval_system)
        tc = ToolCall(id="1", name="fail", arguments={})
        result = await executor.execute(tc)
        assert result.success is False
        assert "bad args" in result.error


class TestConfig:
    def test_default_config(self):
        config = Config()
        assert config.agent.name == "Bahram"
        assert config.memory.enabled is True
        assert config.tools.enabled == ["bash", "read", "write", "edit", "glob", "grep"]

    def test_config_from_dict(self):
        data = {
            "agent": {"name": "Test", "model": "test-model"},
            "providers": {"openai": {"api_key": "sk-test", "models": ["gpt-4o"]}},
        }
        config = Config._from_dict(data)
        assert config.agent.name == "Test"
        assert config.providers["openai"].api_key == "sk-test"
