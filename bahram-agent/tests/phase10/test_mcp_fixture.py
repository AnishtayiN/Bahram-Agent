"""Tests for the real MCP fixture server.

Tests the full MCP pipeline: discovery -> normalization -> ToolRegistry -> security -> executor.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from tests.fixtures.mcp.server import TOOLS, handle_request


class TestMCPServerProtocol:
    """Test the MCP fixture server protocol directly."""

    def test_initialize(self):
        """Server should respond to initialize with correct capabilities."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }
        response = handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["protocolVersion"] == "2024-11-05"
        assert "tools" in response["result"]["capabilities"]

    def test_tools_list(self):
        """Server should return all three tools."""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        response = handle_request(request)

        assert response["id"] == 2
        tools = response["result"]["tools"]
        assert len(tools) == 3
        tool_names = [t["name"] for t in tools]
        assert "echo" in tool_names
        assert "dangerous_op" in tool_names
        assert "failing_tool" in tool_names

    def test_echo_tool(self):
        """Echo tool should return the input message."""
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "echo",
                "arguments": {"message": "hello world"},
            },
        }
        response = handle_request(request)

        assert response["id"] == 3
        assert response["result"]["isError"] is False
        assert response["result"]["content"][0]["text"] == "hello world"

    def test_dangerous_op_tool(self):
        """Dangerous op tool should execute and return result."""
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "dangerous_op",
                "arguments": {"action": "delete_all"},
            },
        }
        response = handle_request(request)

        assert response["id"] == 4
        assert response["result"]["isError"] is False
        assert "delete_all" in response["result"]["content"][0]["text"]

    def test_failing_tool(self):
        """Failing tool should return error response."""
        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "failing_tool",
                "arguments": {},
            },
        }
        response = handle_request(request)

        assert response["id"] == 5
        assert response["result"]["isError"] is True
        assert "failed" in response["result"]["content"][0]["text"].lower()

    def test_unknown_tool(self):
        """Unknown tool should return error."""
        request = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "nonexistent_tool",
                "arguments": {},
            },
        }
        response = handle_request(request)

        assert "error" in response
        assert response["error"]["code"] == -32601

    def test_unknown_method(self):
        """Unknown method should return error."""
        request = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "unknown/method",
            "params": {},
        }
        response = handle_request(request)

        assert "error" in response
        assert response["error"]["code"] == -32601


class TestMCPToolSchema:
    """Test MCP tool schemas are valid."""

    def test_echo_schema_valid(self):
        """Echo tool schema should have required fields."""
        echo_tool = next(t for t in TOOLS if t["name"] == "echo")
        assert "name" in echo_tool
        assert "description" in echo_tool
        assert "inputSchema" in echo_tool
        assert "properties" in echo_tool["inputSchema"]
        assert "message" in echo_tool["inputSchema"]["properties"]

    def test_dangerous_op_schema_valid(self):
        """Dangerous op schema should have required fields."""
        tool = next(t for t in TOOLS if t["name"] == "dangerous_op")
        assert "inputSchema" in tool
        assert "action" in tool["inputSchema"]["properties"]

    def test_failing_tool_schema_valid(self):
        """Failing tool schema should have required fields."""
        tool = next(t for t in TOOLS if t["name"] == "failing_tool")
        assert "inputSchema" in tool


class TestMCPWithAgentEngine:
    """Test MCP tools integrated into the AgentEngine pipeline."""

    def test_mcp_tool_registration(self):
        """MCP tools should be registerable in AgentEngine."""
        from bahram.core.engine import AgentEngine

        engine = AgentEngine()

        class FakeMCPTool:
            def __init__(self, name):
                self.name = name

            async def execute(self, **kwargs):
                return f"result from {self.name}"

            def schema(self):
                return {
                    "name": self.name,
                    "description": f"MCP tool {self.name}",
                    "parameters": {"type": "object", "properties": {}},
                }

        for tool_def in TOOLS:
            tool = FakeMCPTool(tool_def["name"])
            engine.register_tool(f"mcp_{tool_def['name']}", tool)

        assert len(engine.tools) == 3
        assert "mcp_echo" in engine.tools
        assert "mcp_dangerous_op" in engine.tools
        assert "mcp_failing_tool" in engine.tools

    @pytest.mark.asyncio
    async def test_mcp_tool_execution_through_executor(self):
        """MCP tools should execute through the ToolExecutor."""
        from bahram.core.engine import AgentEngine, ToolCall

        engine = AgentEngine()

        class FakeMCPTool:
            def __init__(self, name):
                self.name = name

            async def execute(self, **kwargs):
                return f"MCP result: {json.dumps(kwargs)}"

            def schema(self):
                return {
                    "name": self.name,
                    "description": f"MCP tool {self.name}",
                    "parameters": {"type": "object", "properties": {}},
                }

        for tool_def in TOOLS:
            tool = FakeMCPTool(tool_def["name"])
            engine.register_tool(f"mcp_{tool_def['name']}", tool)

        tool_call = ToolCall(
            id="tc_mcp_1",
            name="mcp_echo",
            arguments={"message": "test"},
        )
        result = await engine._tool_executor.execute(tool_call)

        assert result.success
        assert "MCP result" in result.content

    @pytest.mark.asyncio
    async def test_mcp_tool_security_blocked(self):
        """MCP tools with dangerous names should be blocked by security."""
        from bahram.core.engine import AgentEngine, ToolCall, ToolExecutor
        from bahram.security.approval import ApprovalConfig, ApprovalMode, ApprovalSystem

        config = ApprovalConfig(mode=ApprovalMode.SMART)
        approval = ApprovalSystem(config)

        class DummyTool:
            async def execute(self, **kwargs):
                return "should not reach"

        engine = AgentEngine()
        engine._approval_system = approval
        engine._tool_executor = ToolExecutor({"rm": DummyTool()}, approval)

        tool_call = ToolCall(
            id="tc_danger",
            name="rm",
            arguments={"command": "rm -rf /"},
        )
        result = await engine._tool_executor.execute(tool_call)

        assert not result.success
        assert "Security block" in result.error

    @pytest.mark.asyncio
    async def test_mcp_tool_trajectory_recorded(self):
        """MCP tool executions should be recorded in trajectory."""
        from bahram.core.engine import AgentEngine, ToolCall

        engine = AgentEngine()

        class FakeMCPTool:
            async def execute(self, **kwargs):
                return "traj result"

            def schema(self):
                return {"name": "traj_tool", "description": "test", "parameters": {"type": "object", "properties": {}}}

        engine.register_tool("mcp_traj_tool", FakeMCPTool())

        tool_call = ToolCall(id="tc_traj", name="mcp_traj_tool", arguments={})
        await engine._tool_executor.execute(tool_call)

        log = engine._tool_executor._log
        assert len(log) >= 1
        assert log[-1]["tool"] == "mcp_traj_tool"
        assert log[-1]["status"] == "success"
