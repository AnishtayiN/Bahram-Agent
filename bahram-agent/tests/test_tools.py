from __future__ import annotations

import pytest
import asyncio

from bahram.tools.base import BaseTool, ToolSchema


class TestToolSchema:
    def test_create_schema(self):
        schema = ToolSchema(name="test", description="A test tool", parameters={"type": "object", "properties": {}})
        assert schema.name == "test"
        assert schema.to_dict()["name"] == "test"


class ConcreteTool(BaseTool):
    @property
    def name(self) -> str:
        return "concrete_tool"

    @property
    def description(self) -> str:
        return "A concrete test tool"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}

    async def execute(self, **kwargs) -> str:
        return f"Executed with: {kwargs.get('text', '')}"


class TestBaseTool:
    def test_schema(self):
        tool = ConcreteTool()
        schema = tool.schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "concrete_tool"

    def test_validate_args(self):
        tool = ConcreteTool()
        assert tool.validate_args(text="hello") is True

    def test_validate_missing_required(self):
        tool = ConcreteTool()
        with pytest.raises(ValueError, match="Missing required parameter"):
            tool.validate_args()

    @pytest.mark.asyncio
    async def test_execute(self):
        tool = ConcreteTool()
        result = await tool.execute(text="hello")
        assert "hello" in result
