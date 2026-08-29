"""Base skill class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SkillMetadata:
    """Metadata for a skill."""

    name: str
    description: str
    version: str = "1.0.0"
    author: str = "Bahram"
    tags: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)


class BaseSkill(ABC):
    """Base class for all skills."""

    @property
    @abstractmethod
    def metadata(self) -> SkillMetadata:
        """Get skill metadata."""
        ...

    @abstractmethod
    async def execute(self, context: dict[str, Any]) -> str:
        """Execute the skill."""
        ...

    async def can_handle(self, task: str) -> bool:
        """Check if this skill can handle the given task."""
        task_lower = task.lower()
        return any(trigger.lower() in task_lower for trigger in self.metadata.triggers)

    async def get_help(self) -> str:
        """Get help text for this skill."""
        return f"""Skill: {self.metadata.name}
Description: {self.metadata.description}
Version: {self.metadata.version}
Tags: {', '.join(self.metadata.tags)}
"""
