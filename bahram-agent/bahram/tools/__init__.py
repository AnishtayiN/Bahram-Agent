from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

async def init_tools(engine: Any, config: Any) -> None:
    tools_config = config.tools
    disabled = set(tools_config.disabled) if hasattr(tools_config, 'disabled') else set()

    tool_list: list[tuple[str, Any]] = []

    try:
        from bahram.tools.bash import BashTool
        tool_list.append(("bash", BashTool(config=tools_config)))
    except Exception as e:
        logger.warning(f"Failed to load bash tool: {e}")

    try:
        from bahram.tools.file import ReadTool, WriteTool, EditTool
        tool_list.append(("read", ReadTool()))
        tool_list.append(("write", WriteTool(config=tools_config)))
        tool_list.append(("edit", EditTool()))
    except Exception as e:
        logger.warning(f"Failed to load file tools: {e}")

    try:
        from bahram.tools.web import WebFetchTool, WebSearchTool
        tool_list.append(("webfetch", WebFetchTool(config=tools_config)))
        tool_list.append(("websearch", WebSearchTool(config=tools_config)))
    except Exception as e:
        logger.warning(f"Failed to load web tools: {e}")

    try:
        from bahram.tools.execute_code import ExecuteCodeTool
        tool_list.append(("execute_code", ExecuteCodeTool()))
    except Exception as e:
        logger.warning(f"Failed to load execute_code tool: {e}")

    try:
        from bahram.tools.extended import GitTool, ProcessListTool, ContainerTool, DocumentReadTool
        tool_list.append(("git", GitTool()))
        tool_list.append(("process_list", ProcessListTool()))
        tool_list.append(("container", ContainerTool()))
        tool_list.append(("document_read", DocumentReadTool()))
    except Exception as e:
        logger.warning(f"Failed to load extended tools: {e}")

    for name, tool in tool_list:
        if name in disabled:
            continue
        engine.register_tool(name, tool)

    logger.info(f"Registered {len(engine.tools)} tools: {list(engine.tools.keys())}")
