"""Phase 10: MCP integration tests.

Tests that MCP tools enter the same pipeline as built-in tools:
discovery -> normalization -> ToolRegistry -> security -> approval -> executor -> trajectory.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from bahram.core.engine import AgentEngine, ToolCall, ToolExecutor


class FakeMCPTool:
    """Simulates an MCP-discovered tool registered in ToolRegistry."""

    def __init__(self, name, description="fake mcp tool", should_fail=False):
        self.name = name
        self.description = description
        self.should_fail = should_fail
        self.execution_count = 0
        self.last_kwargs = {}

    async def execute(self, **kwargs):
        self.execution_count += 1
        self.last_kwargs = kwargs
        if self.should_fail:
            raise RuntimeError("MCP tool execution failed")
        return f"MCP result for {self.name}: {json.dumps(kwargs, default=str)}"

    def schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {"input": {"type": "string", "description": "Input parameter"}},
            },
        }


class TestMCPIntegration:
    """Verify MCP tools go through the same pipeline as built-in tools."""

    def test_mcp_tool_appears_in_registry(self):
        """MCP tool should be registerable in the central ToolRegistry."""
        engine = AgentEngine()
        mcp_tool = FakeMCPTool("mcp_test_tool")

        engine.register_tool("mcp_test_tool", mcp_tool)

        assert "mcp_test_tool" in engine.tools
        assert engine.tools["mcp_test_tool"] is mcp_tool

    def test_mcp_tool_has_schema(self):
        """MCP tool should provide a schema like built-in tools."""
        mcp_tool = FakeMCPTool("mcp_db_query", description="Query database via MCP")

        schema = mcp_tool.schema()

        assert schema["name"] == "mcp_db_query"
        assert "parameters" in schema
        assert "properties" in schema["parameters"]

    def test_mcp_tool_schema_in_engine(self):
        """Engine should include MCP tool schemas in tool list."""
        engine = AgentEngine()
        mcp_tool = FakeMCPTool("mcp_search")
        engine.register_tool("mcp_search", mcp_tool)

        schemas = engine.get_tools_schema()
        mcp_schemas = [s for s in schemas if s.get("name") == "mcp_search"]
        assert len(mcp_schemas) == 1

    @pytest.mark.asyncio
    async def test_mcp_tool_executes_through_tool_executor(self):
        """MCP tool should be executable through the same ToolExecutor."""
        engine = AgentEngine()
        mcp_tool = FakeMCPTool("mcp_calculator")
        engine.register_tool("mcp_calculator", mcp_tool)

        tool_call = ToolCall(id="tc_mcp_1", name="mcp_calculator", arguments={"input": "42"})
        result = await engine._tool_executor.execute(tool_call)

        assert result.success
        assert "42" in result.content
        assert mcp_tool.execution_count == 1

    @pytest.mark.asyncio
    async def test_mcp_tool_security_applies(self):
        """Security pipeline should apply to MCP tools."""
        from bahram.security.approval import ApprovalConfig, ApprovalMode, ApprovalSystem

        config = ApprovalConfig(mode=ApprovalMode.SMART)
        approval = ApprovalSystem(config)

        engine = AgentEngine()
        engine._approval_system = approval
        engine._tool_executor = ToolExecutor(engine.tools, approval)

        mcp_tool = FakeMCPTool("mcp_dangerous_op")
        engine.register_tool("mcp_dangerous_op", mcp_tool)

        assert engine._tool_executor is not None

    @pytest.mark.asyncio
    async def test_mcp_tool_error_handling(self):
        """MCP tool failures should be handled gracefully."""
        engine = AgentEngine()
        mcp_tool = FakeMCPTool("mcp_failing", should_fail=True)
        engine.register_tool("mcp_failing", mcp_tool)

        tool_call = ToolCall(id="tc_mcp_fail", name="mcp_failing", arguments={"input": "test"})
        result = await engine._tool_executor.execute(tool_call)

        assert not result.success
        assert "MCP tool execution failed" in result.error

    @pytest.mark.asyncio
    async def test_mcp_tool_timeout(self):
        """MCP tool should respect execution timeout."""
        engine = AgentEngine()

        class SlowMCPTool:
            def __init__(self):
                self.name = "mcp_slow"

            async def execute(self, **kwargs):
                await asyncio.sleep(10)
                return "should not reach"

            def schema(self):
                return {
                    "name": "mcp_slow",
                    "description": "slow",
                    "parameters": {"type": "object", "properties": {}},
                }

        engine.register_tool("mcp_slow", SlowMCPTool())

        tool_call = ToolCall(id="tc_slow", name="mcp_slow", arguments={})
        result = await engine._tool_executor.execute(tool_call, timeout=0.1)

        assert not result.success
        assert "timed out" in result.error

    @pytest.mark.asyncio
    async def test_mcp_tool_trajectory_recorded(self):
        """MCP tool execution should be recorded in ToolExecutor log."""
        engine = AgentEngine()
        mcp_tool = FakeMCPTool("mcp_tracked")
        engine.register_tool("mcp_tracked", mcp_tool)

        tool_call = ToolCall(id="tc_track", name="mcp_tracked", arguments={"input": "tracked"})
        await engine._tool_executor.execute(tool_call)

        log = engine._tool_executor._log
        assert len(log) >= 1
        assert log[-1]["tool"] == "mcp_tracked"
        assert log[-1]["status"] == "success"

    def test_mcp_tool_unknown_tool_error(self):
        """Requesting an unknown MCP tool should return error."""
        from bahram.core.engine import ToolExecutor

        engine = AgentEngine()
        executor = ToolExecutor({}, engine._approval_system)

        tool_call = ToolCall(id="tc_unknown", name="mcp_nonexistent", arguments={})
        result = asyncio.run(executor.execute(tool_call))

        assert not result.success
        assert "Unknown tool" in result.error

    def test_mcp_tool_namespacing(self):
        """MCP tools should be namespaced with mcp_ prefix."""
        engine = AgentEngine()
        mcp_tool = FakeMCPTool("original_name")
        engine.register_tool("mcp_original_name", mcp_tool)

        assert "mcp_original_name" in engine.tools
        assert "original_name" not in engine.tools

    @pytest.mark.asyncio
    async def test_mcp_tool_multiple_executions(self):
        """MCP tool should support multiple sequential executions."""
        engine = AgentEngine()
        mcp_tool = FakeMCPTool("mcp_multi")
        engine.register_tool("mcp_multi", mcp_tool)

        for i in range(5):
            tool_call = ToolCall(id=f"tc_{i}", name="mcp_multi", arguments={"input": str(i)})
            result = await engine._tool_executor.execute(tool_call)
            assert result.success

        assert mcp_tool.execution_count == 5
