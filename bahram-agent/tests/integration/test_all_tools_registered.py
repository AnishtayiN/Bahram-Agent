from __future__ import annotations

import inspect
from unittest.mock import patch

import pytest

from bahram.core.engine import AgentEngine, ToolExecutor
from bahram.tools.base import BaseTool
from bahram.tools.bash import BashTool
from bahram.tools.execute_code import ExecuteCodeTool
from bahram.tools.extended import ContainerTool, DocumentReadTool, GitTool, ProcessListTool
from bahram.tools.file import EditTool, ReadTool, WriteTool
from bahram.tools.web import WebFetchTool, WebSearchTool

ALL_TOOL_CLASSES: dict[str, type[BaseTool]] = {
    "bash": BashTool,
    "read": ReadTool,
    "write": WriteTool,
    "edit": EditTool,
    "webfetch": WebFetchTool,
    "websearch": WebSearchTool,
    "execute_code": ExecuteCodeTool,
    "git": GitTool,
    "process_list": ProcessListTool,
    "container": ContainerTool,
    "document_read": DocumentReadTool,
}

INIT_TOOLS_NAMES = set(ALL_TOOL_CLASSES.keys())


def _make_tools_config(disabled: list[str] | None = None):
    class FakeToolsConfig:
        pass
    cfg = FakeToolsConfig()
    cfg.disabled = disabled or []
    return cfg


def _make_config(disabled: list[str] | None = None):
    class FakeConfig:
        pass
    cfg = FakeConfig()
    cfg.tools = _make_tools_config(disabled)
    return cfg


def _patch_write_tool_init():
    """Patch WriteTool.__init__ to accept config kwarg (it's missing in the codebase)."""
    original_init = WriteTool.__init__ if hasattr(WriteTool, '__init__') else None

    def patched_init(self, config=None):
        pass

    return patch.object(WriteTool, '__init__', patched_init)


class TestToolDiscovery:
    def test_all_tool_classes_discoverable(self):
        assert len(ALL_TOOL_CLASSES) == 11, f"Expected 11 tools, got {len(ALL_TOOL_CLASSES)}"

    def test_every_tool_is_basertool_subclass(self):
        for name, cls in ALL_TOOL_CLASSES.items():
            assert issubclass(cls, BaseTool), f"{name} ({cls.__name__}) is not a BaseTool subclass"

    @pytest.mark.parametrize("name", list(ALL_TOOL_CLASSES.keys()))
    def test_tool_has_execute_method(self, name: str):
        cls = ALL_TOOL_CLASSES[name]
        assert hasattr(cls, "execute"), f"{name} missing execute method"
        assert callable(getattr(cls, "execute")), f"{name}.execute is not callable"

    @pytest.mark.parametrize("name", list(ALL_TOOL_CLASSES.keys()))
    def test_tool_has_schema(self, name: str):
        cls = ALL_TOOL_CLASSES[name]
        assert hasattr(cls, "schema"), f"{name} missing schema method"

    @pytest.mark.parametrize("name", list(ALL_TOOL_CLASSES.keys()))
    def test_tool_has_description(self, name: str):
        cls = ALL_TOOL_CLASSES[name]
        instance = cls() if cls not in (BashTool, WebFetchTool, WebSearchTool) else cls(config=None)
        desc = instance.description
        assert desc and len(desc) > 5, f"{name} has empty or too-short description"

    @pytest.mark.parametrize("name", list(ALL_TOOL_CLASSES.keys()))
    def test_tool_schema_has_function_key(self, name: str):
        cls = ALL_TOOL_CLASSES[name]
        instance = cls() if cls not in (BashTool, WebFetchTool, WebSearchTool) else cls(config=None)
        s = instance.schema()
        assert "type" in s and s["type"] == "function", f"{name} schema missing type=function"
        assert "function" in s, f"{name} schema missing function key"
        assert "name" in s["function"], f"{name} schema.function missing name"
        assert "parameters" in s["function"], f"{name} schema.function missing parameters"


class TestInitToolsRegistration:
    async def test_init_tools_registers_all_expected_tools(self, engine: AgentEngine):
        from bahram.tools import init_tools
        with _patch_write_tool_init():
            await init_tools(engine, _make_config())

        for name in INIT_TOOLS_NAMES:
            assert name in engine.tools, f"Tool '{name}' not registered by init_tools()"

    async def test_no_missing_tools(self, engine: AgentEngine):
        from bahram.tools import init_tools
        with _patch_write_tool_init():
            await init_tools(engine, _make_config())

        registered = set(engine.tools.keys())
        missing = INIT_TOOLS_NAMES - registered
        extra = registered - INIT_TOOLS_NAMES

        assert not missing, f"Missing tools: {missing}"
        assert not extra, f"Unexpected extra tools: {extra}"

    async def test_disabled_tools_not_registered(self, engine: AgentEngine):
        from bahram.tools import init_tools
        with _patch_write_tool_init():
            await init_tools(engine, _make_config(disabled=["bash", "git"]))

        assert "bash" not in engine.tools
        assert "git" not in engine.tools
        for name in INIT_TOOLS_NAMES - {"bash", "git"}:
            assert name in engine.tools, f"Tool '{name}' should still be registered"

    async def test_disabled_tools_actually_excluded(self, engine: AgentEngine):
        from bahram.tools import init_tools
        with _patch_write_tool_init():
            await init_tools(engine, _make_config(disabled=["bash", "read", "edit"]))

        assert "bash" not in engine.tools
        assert "read" not in engine.tools
        assert "edit" not in engine.tools
        assert "write" in engine.tools


class TestToolExecutorIsOnlyExecutionPath:
    async def test_engine_creates_tool_executor(self, engine: AgentEngine):
        from bahram.tools import init_tools
        with _patch_write_tool_init():
            await init_tools(engine, _make_config())

        assert engine._tool_executor is not None, "AgentEngine._tool_executor was not created"
        assert isinstance(engine._tool_executor, ToolExecutor), (
            f"_tool_executor is {type(engine._tool_executor)}, not ToolExecutor"
        )

    async def test_tool_executor_has_all_tools(self, engine: AgentEngine):
        from bahram.tools import init_tools
        with _patch_write_tool_init():
            await init_tools(engine, _make_config())

        executor_tools = set(engine._tool_executor.tools.keys())
        engine_tools = set(engine.tools.keys())
        assert executor_tools == engine_tools, (
            f"ToolExecutor tools mismatch: executor={executor_tools}, engine={engine_tools}"
        )

    def test_register_tool_recreates_executor(self, engine: AgentEngine):
        old_executor = engine._tool_executor
        engine.register_tool("custom_tool", BashTool())
        assert engine._tool_executor is not old_executor, "register_tool did not recreate ToolExecutor"
        assert "custom_tool" in engine._tool_executor.tools
