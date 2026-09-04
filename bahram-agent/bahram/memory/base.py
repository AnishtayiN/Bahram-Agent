from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class MemoryEntry:

    id: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5
    access_count: int = 0
    last_accessed: datetime | None = None

class BaseMemory(ABC):

    @abstractmethod
    async def add(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        ...

    @abstractmethod
    async def get(self, memory_id: str) -> MemoryEntry | None:
        ...

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        ...

    @abstractmethod
    async def update(self, memory_id: str, content: str) -> bool:
        ...

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        ...

    @abstractmethod
    async def list_all(self, limit: int = 100) -> list[MemoryEntry]:
        ...

    @abstractmethod
    async def clear(self) -> None:
        ...

    def calculate_importance(self, content: str, metadata: dict[str, Any]) -> float:

        score = 0.5

        if any(
            keyword in content.lower()
            for keyword in ["function", "class", "import", "def", "async"]
        ):
            score += 0.1

        if any(keyword in content.lower() for keyword in ["error", "fix", "bug", "issue"]):
            score += 0.1

        if metadata.get("type") == "preference":
            score += 0.2

        if metadata.get("type") == "task_complete":
            score += 0.15

        return min(score, 1.0)
