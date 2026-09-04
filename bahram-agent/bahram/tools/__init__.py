"""Tool package for the Bahram agent.

This module is the single entry point used by
:class:`bahram.core.agent.Agent` to build the tool registry that is handed
to :class:`bahram.core.engine.AgentEngine`.

Design notes
------------
* :func:`init_tools` registers the **core** tool set (11 tools) that is
  always available and safe by default.
* :func:`discover_tool_classes` walks every module in this package and
  collects concrete :class:`~bahram.tools.base.BaseTool` subclasses, so the
  registry cannot silently drift away from the code that lives next to it.
* Construction failures are **never** silently swallowed any more.  They are
  logged with ``logger.exception`` and, when ``strict=True``, re-raised.  A
  previous implementation downgraded every failure to ``logger.warning``,
  which hid a ``TypeError`` from ``WriteTool(config=...)`` and meant that
  ``write``/``edit`` never reached the production registry.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import Any

from bahram.tools.base import BaseTool

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_TOOL_NAMES",
    "ToolLoadError",
    "discover_tool_classes",
    "init_tools",
]


class ToolLoadError(RuntimeError):
    """Raised by :func:`init_tools` when ``strict=True`` and a tool fails."""


#: The tool names registered by default.  Kept as a module level constant so
#: tests can assert the registry invariant without re-implementing the list.
DEFAULT_TOOL_NAMES: tuple[str, ...] = (
    "bash",
    "read",
    "write",
    "edit",
    "webfetch",
    "websearch",
    "execute_code",
    "git",
    "process_list",
    "container",
    "document_read",
)


def _disabled_names(config: Any) -> set[str]:
    """Return the set of tool names disabled via ``config.tools.disabled``."""
    tools_config = getattr(config, "tools", None)
    disabled = getattr(tools_config, "disabled", None) or ()
    return set(disabled)


def _build_core_tools(tools_config: Any) -> list[tuple[str, BaseTool]]:
    """Instantiate the core tool set.

    Every tool is accepted through the uniform ``(config=...)`` keyword, which
    is safe because :class:`~bahram.tools.base.BaseTool` now defines a
    permissive ``__init__``.
    """
    # Imported lazily so that a broken optional dependency in one module
    # cannot prevent the rest of the package from importing.
    from bahram.tools.bash import BashTool
    from bahram.tools.execute_code import ExecuteCodeTool
    from bahram.tools.extended import (
        ContainerTool,
        DocumentReadTool,
        GitTool,
        ProcessListTool,
    )
    from bahram.tools.file import EditTool, ReadTool, WriteTool
    from bahram.tools.web import WebFetchTool, WebSearchTool

    return [
        ("bash", BashTool(config=tools_config)),
        ("read", ReadTool(config=tools_config)),
        ("write", WriteTool(config=tools_config)),
        ("edit", EditTool(config=tools_config)),
        ("webfetch", WebFetchTool(config=tools_config)),
        ("websearch", WebSearchTool(config=tools_config)),
        ("execute_code", ExecuteCodeTool(config=tools_config)),
        ("git", GitTool(config=tools_config)),
        ("process_list", ProcessListTool(config=tools_config)),
        ("container", ContainerTool(config=tools_config)),
        ("document_read", DocumentReadTool(config=tools_config)),
    ]


def discover_tool_classes() -> dict[str, type[BaseTool]]:
    """Import every module in :mod:`bahram.tools` and collect tool classes.

    Returns:
        Mapping of ``tool.name`` to the concrete :class:`BaseTool` subclass
        that implements it.  Only classes that are defined *inside* this
        package are returned (imported aliases are ignored) and every class
        must be instantiable with no arguments.
    """
    found: dict[str, type[BaseTool]] = {}
    package = __name__
    for _finder, mod_name, _ispkg in pkgutil.iter_modules(__path__):
        if mod_name == "base":
            continue
        try:
            module = importlib.import_module(f"{package}.{mod_name}")
        except Exception:
            # A module that cannot be imported simply contributes no tools.
            logger.warning("Skipping tool module %s: import failed", mod_name, exc_info=True)
            continue
        for _attr, obj in vars(module).items():
            if not inspect.isclass(obj) or not issubclass(obj, BaseTool):
                continue
            if obj is BaseTool or inspect.isabstract(obj):
                continue
            if getattr(obj, "__module__", "").split(".")[:2] != ["bahram", "tools"]:
                continue
            try:
                name = obj().name
            except Exception:
                logger.warning("Skipping tool class %s: cannot read name", obj, exc_info=True)
                continue
            found[name] = obj
    return found


async def init_tools(engine: Any, config: Any, strict: bool = False) -> list[str]:
    """Register the default tool set on ``engine``.

    Args:
        engine: Object exposing ``register_tool(name, tool)`` (an
            :class:`~bahram.core.engine.AgentEngine`).
        config: Agent configuration; ``config.tools.disabled`` is honoured.
        strict: When ``True`` a tool that fails to construct or register is
            re-raised as :class:`ToolLoadError` instead of being skipped.

    Returns:
        The list of tool names that were registered, in registration order.

    Raises:
        ToolLoadError: If ``strict`` is set and any tool could not be loaded.
    """
    tools_config = getattr(config, "tools", None)
    disabled = _disabled_names(config)

    registered: list[str] = []
    failures: list[str] = []

    for name, tool in _build_core_tools(tools_config):
        if name in disabled:
            logger.info("Tool %s disabled by configuration", name)
            continue
        try:
            engine.register_tool(name, tool)
        except Exception:
            logger.exception("Failed to register tool %s", name)
            if strict:
                raise ToolLoadError(f"Failed to register tool {name}") from None
            failures.append(name)
            continue
        registered.append(name)

    if failures:
        logger.error(
            "Tool registration incomplete; %d tool(s) failed: %s",
            len(failures),
            ", ".join(failures),
        )
    if strict:
        missing = [n for n in DEFAULT_TOOL_NAMES if n not in registered and n not in disabled]
        if missing:
            raise ToolLoadError(f"Core tools missing from registry: {sorted(missing)}")

    logger.info("Registered %d tools: %s", len(registered), registered)
    return registered
