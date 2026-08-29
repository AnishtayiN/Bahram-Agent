"""Base memory class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class MemoryEntry:
    """A single memory entry."""

    id: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5  # 0.0 to 1.0
    access_count: int = 0
    last_accessed: Optional[datetime] = None


class BaseMemory(ABC):
    """Base class for memory systems."""

    @abstractmethod
    async def add(self, content: str, metadata: Optional[dict[str, Any]] = None) -> str:
        """Add a memory entry."""
        ...

    @abstractmethod
    async def get(self, memory_id: str) -> Optional[MemoryEntry]:
        """Get a memory by ID."""
        ...

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Search memories."""
        ...

    @abstractmethod
    async def update(self, memory_id: str, content: str) -> bool:
        """Update a memory entry."""
        ...

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """Delete a memory entry."""
        ...

    @abstractmethod
    async def list_all(self, limit: int = 100) -> list[MemoryEntry]:
        """List all memories."""
        ...

    @abstractmethod
    async def clear(self) -> None:
        """Clear all memories."""
        ...

    def calculate_importance(self, content: str, metadata: dict[str, Any]) -> float:
        """Calculate importance score for a memory."""
        # Simple heuristic - can be improved with LLM
        score = 0.5

        # Boost for code-related content
        if any(
            keyword in content.lower()
            for keyword in ["function", "class", "import", "def", "async"]
        ):
            score += 0.1

        # Boost for error/fix related content
        if any(keyword in content.lower() for keyword in ["error", "fix", "bug", "issue"]):
            score += 0.1

        # Boost for user preferences
        if metadata.get("type") == "preference":
            score += 0.2

        # Boost for task completion
        if metadata.get("type") == "task_complete":
            score += 0.15

        return min(score, 1.0)
