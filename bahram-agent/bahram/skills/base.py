"""
Base.

Public objects: ``SkillMetadata``, ``BaseSkill``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillMetadata:
    """
    Skill metadata.

    Attributes:
        name (str): name of the object.
        description (str): human readable description.
        version (str): version string.
        author (str): author string.
        tags (list[str]): collection of tags.
        triggers (list[str]): collection of triggers.
    """

    name: str
    description: str
    version: str = "1.0.0"
    author: str = "Bahram"
    tags: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)


class BaseSkill(ABC):
    """
    Base skill.
    """

    @property
    @abstractmethod
    def metadata(self) -> SkillMetadata:
        """Static description of the skill.

        Returns:
            SkillMetadata: name, description and trigger phrases.
        """
        ...

    @abstractmethod
    async def execute(self, context: dict[str, Any]) -> str:
        """Run the skill.

        Args:
            context (dict[str, Any]): invocation context (task, arguments,
                memory, ...).

        Returns:
            str: the skill's textual result.

        Note:
            Coroutine - must be awaited.
        """
        ...

    async def can_handle(self, task: str) -> bool:
        """
        Return ``True`` when the object can handle.

        Args:
            task (str): task string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        task_lower = task.lower()
        return any(trigger.lower() in task_lower for trigger in self.metadata.triggers)

    async def get_help(self) -> str:
        """
        Return the help.

        Returns:
            str: the rendered string.

        Note:
            Coroutine - must be awaited.
        """
        return ""
