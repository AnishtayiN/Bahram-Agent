"""Tool abstractions shared by every Bahram tool.

Public objects: ``ToolSchema``, ``BaseTool``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolSchema:
    """
    Tool schema.

    Attributes:
        name (str): name of the object.
        description (str): human readable description.
        parameters (dict[str, Any]): mapping of parameters.
    """

    name: str
    description: str
    parameters: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """
        Serialise the object to a JSON-serialisable dictionary.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
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
        """
        Initialise a BaseTool instance.

        Args:
            config (Any): configuration object. Defaults to ``None``.
        """
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Registry name of the tool, e.g. ``bash``.

        Returns:
            str: the name the model uses in ``tool_calls``.
        """
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """One-sentence description shown to the model in the tool schema.

        Returns:
            str: human readable description of what the tool does.
        """
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema describing the keyword arguments :meth:`execute` takes.

        Returns:
            dict[str, Any]: an ``{"type": "object", ...}`` JSON Schema.
        """
        ...

    def schema(self) -> dict[str, Any]:
        """
        Return the OpenAI-style function schema for this tool.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
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
        """Run the tool.

        Args:
            **kwargs (Any): arguments described by :attr:`parameters`.

        Returns:
            str: the textual result handed back to the model.  Implementations
                return an ``"Error: ..."`` string instead of raising, so that a
                failure becomes model-visible feedback rather than a crash.

        Note:
            Coroutine - must be awaited.
        """
        ...

    def validate_args(self, **kwargs: Any) -> bool:
        """
        Validate the supplied keyword arguments against the parameter schema.

        Args:
            **kwargs (Any): keyword arguments forwarded to the implementation.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Raises:
            ValueError: if the operation cannot be completed.
        """
        required = self.parameters.get("required", [])
        for param in required:
            if param not in kwargs:
                raise ValueError(f"Missing required parameter: {param}")
        return True
