from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SkillMetadata:

    name: str
    description: str
    version: str = "1.0.0"
    author: str = "Bahram"
    tags: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)

class BaseSkill(ABC):

    @property
    @abstractmethod
    def metadata(self) -> SkillMetadata:
        ...

    @abstractmethod
    async def execute(self, context: dict[str, Any]) -> str:
        ...

    async def can_handle(self, task: str) -> bool:
        task_lower = task.lower()
        return any(trigger.lower() in task_lower for trigger in self.metadata.triggers)

    async def get_help(self) -> str:
        return ""
