"""Tools system for Bahram Agent."""

from bahram.tools.base import BaseTool
from bahram.tools.bash import BashTool
from bahram.tools.file import ReadTool, WriteTool, EditTool

__all__ = [
    "BaseTool",
    "BashTool",
    "ReadTool",
    "WriteTool",
    "EditTool",
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
