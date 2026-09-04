from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolSchema:

    name: str
    description: str
    parameters: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

class BaseTool(ABC):
    """Abstract base class for every Bahram tool.

    Subclasses must implement :attr:`name`, :attr:`description`,
    :attr:`parameters` (all read-only properties) and the coroutine
    :meth:`execute`.

    The base class deliberately provides a permissive ``__init__`` that
    accepts an optional ``config`` object.  Tools that need configuration
    (for example :class:`bahram.tools.bash.BashTool`, which reads
    ``bash_timeout``) override it and call ``super().__init__(config)``.
    Tools that ignore configuration simply inherit this constructor, which
    means the tool registry can build *every* tool with the uniform call
    ``ToolCls(config=tools_config)`` without raising ``TypeError``.
    """

    def __init__(self, config: Any = None) -> None:
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        ...

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        ...

    def validate_args(self, **kwargs: Any) -> bool:

        required = self.parameters.get("required", [])
        for param in required:
            if param not in kwargs:
                raise ValueError(f"Missing required parameter: {param}")
        return True
