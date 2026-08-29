"""Tools system for Bahram Agent."""

from bahram.tools.base import BaseTool
from bahram.tools.bash import BashTool
from bahram.tools.file import ReadTool, WriteTool, EditTool
from bahram.tools.search import GlobTool, GrepTool
from bahram.tools.web import WebFetchTool, WebSearchTool
from bahram.tools.task import TaskTool

__all__ = [
    "BaseTool",
    "BashTool",
    "ReadTool",
    "WriteTool",
    "EditTool",
    "GlobTool",
    "GrepTool",
    "WebFetchTool",
    "WebSearchTool",
    "TaskTool",
]


async def init_tools(engine: "AgentEngine", config: "Config") -> None:
    """Initialize all tools."""
    tools_config = config.tools

    if "bash" in tools_config.enabled:
        engine.register_tool("bash", BashTool(config=tools_config))
    if "read" in tools_config.enabled:
        engine.register_tool("read", ReadTool())
    if "write" in tools_config.enabled:
        engine.register_tool("write", WriteTool())
    if "edit" in tools_config.enabled:
        engine.register_tool("edit", EditTool())
    if "glob" in tools_config.enabled:
        engine.register_tool("glob", GlobTool())
    if "grep" in tools_config.enabled:
        engine.register_tool("grep", GrepTool())
    if "webfetch" in tools_config.enabled:
        engine.register_tool("webfetch", WebFetchTool(config=tools_config))
    if "websearch" in tools_config.enabled:
        engine.register_tool("websearch", WebSearchTool(config=tools_config))
    if "task" in tools_config.enabled:
        engine.register_tool("task", TaskTool())
