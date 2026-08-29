"""Base plugin class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class PluginMetadata:
    """Plugin metadata."""

    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    hooks: list[str] = field(default_factory=list)


class BasePlugin(ABC):
    """Base class for plugins."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        ...

    @abstractmethod
    async def register(self, context: Any) -> None:
        """Register the plugin with the agent."""
        ...

    async def on_startup(self) -> None:
        """Called when the agent starts."""
        pass

    async def on_shutdown(self) -> None:
        """Called when the agent stops."""
        pass

    async def on_message(self, message: Any) -> Optional[Any]:
        """Called when a message is received."""
        pass

    async def on_tool_call(self, tool_name: str, arguments: dict) -> Optional[dict]:
        """Called before a tool is executed."""
        pass

    async def on_tool_result(self, tool_name: str, result: Any) -> Optional[Any]:
        """Called after a tool is executed."""
        pass

    async def on_error(self, error: Exception) -> None:
        """Called when an error occurs."""
        pass
