"""
Base.

Public objects: ``PluginMetadata``, ``BasePlugin``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PluginMetadata:
    """
    Plugin metadata.

    Attributes:
        name (str): name of the object.
        version (str): version string.
        description (str): human readable description.
        author (str): author string.
        hooks (list[str]): collection of hooks.
    """

    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    hooks: list[str] = field(default_factory=list)


class BasePlugin(ABC):
    """
    Base plugin.
    """

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Static description of the plugin.

        Returns:
            PluginMetadata: name, version and declared hooks.
        """
        ...

    @abstractmethod
    async def register(self, context: Any) -> None:
        """Register the plugin's tools and hooks on ``context``.

        Args:
            context (Any): the agent/application context handed to plugins.

        Note:
            Coroutine - must be awaited.
        """
        ...

    async def on_startup(self) -> None:
        """
        Hook invoked when startup.

        Default: no-op. Subclasses override the hooks they care about.

        Note:
            Coroutine - must be awaited.
        """
        pass

    async def on_shutdown(self) -> None:
        """
        Hook invoked when shutdown.

        Default: no-op. Subclasses override the hooks they care about.

        Note:
            Coroutine - must be awaited.
        """
        pass

    async def on_message(self, message: Any) -> Any | None:
        """
        Hook invoked when message.
        Default: no-op. Subclasses override the hooks they care about.

        Args:
            message (Any): message to process.

        Returns:
            Any | None: the resulting object, or ``None`` when it is not available.

        Note:
            Coroutine - must be awaited.
        """
        pass

    async def on_tool_call(self, tool_name: str, arguments: dict) -> dict | None:
        """
        Hook invoked when tool call.
        Default: no-op. Subclasses override the hooks they care about.

        Args:
            tool_name (str): tool name string.
            arguments (dict): mapping of arguments.

        Returns:
            dict | None: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        pass

    async def on_tool_result(self, tool_name: str, result: Any) -> Any | None:
        """
        Hook invoked when tool result.
        Default: no-op. Subclasses override the hooks they care about.

        Args:
            tool_name (str): tool name string.
            result (Any): result.

        Returns:
            Any | None: the resulting object, or ``None`` when it is not available.

        Note:
            Coroutine - must be awaited.
        """
        pass

    async def on_error(self, error: Exception) -> None:
        """
        Hook invoked when error.
        Default: no-op. Subclasses override the hooks they care about.

        Args:
            error (Exception): error.

        Note:
            Coroutine - must be awaited.
        """
        pass
