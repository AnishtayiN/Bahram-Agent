from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class ToolSchema:
    ""

    name: str
    description: str
    parameters: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        ""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

class BaseTool(ABC):
    ""

    @property
    @abstractmethod
    def name(self) -> str:
        ""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ""
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        ""
        ...

    def schema(self) -> dict[str, Any]:
        ""
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
        ""
        ...

    def validate_args(self, **kwargs: Any) -> bool:
        ""

        required = self.parameters.get("required", [])
        for param in required:
            if param not in kwargs:
                raise ValueError(f"Missing required parameter: {param}")
        return True
