from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

@dataclass
class PluginMetadata:

    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    hooks: list[str] = field(default_factory=list)

class BasePlugin(ABC):

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        ...

    @abstractmethod
    async def register(self, context: Any) -> None:
        ...

    async def on_startup(self) -> None:
        pass

    async def on_shutdown(self) -> None:
        pass

    async def on_message(self, message: Any) -> Optional[Any]:
        pass

    async def on_tool_call(self, tool_name: str, arguments: dict) -> Optional[dict]:
        pass

    async def on_tool_result(self, tool_name: str, result: Any) -> Optional[Any]:
        pass

    async def on_error(self, error: Exception) -> None:
        pass
