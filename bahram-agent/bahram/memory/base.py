"""
Base.

Public objects: ``MemoryEntry``, ``BaseMemory``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MemoryEntry:
    """
    Memory entry.

    Attributes:
        id (str): id string.
        content (str): text content to process.
        timestamp (datetime): timestamp.
        metadata (dict[str, Any]): mapping of metadata.
        importance (float): numeric value for importance.
        access_count (int): numeric value for access count.
        last_accessed (datetime | None): last accessed.
    """

    id: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5
    access_count: int = 0
    last_accessed: datetime | None = None


class BaseMemory(ABC):
    """
    Base memory.
    """

    @abstractmethod
    async def add(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """Store a new memory and return its identifier.

        Args:
            content (str): text content to process.
            metadata (dict[str, Any] | None): optional structured metadata.
                Defaults to ``None``.

        Returns:
            str: the id of the newly created memory entry.

        Note:
            Coroutine - must be awaited.
        """
        ...

    @abstractmethod
    async def get(self, memory_id: str) -> MemoryEntry | None:
        """Return a single memory entry by id.

        Args:
            memory_id (str): memory identifier.

        Returns:
            MemoryEntry | None: the entry, or ``None`` when it does not exist.

        Note:
            Coroutine - must be awaited.
        """
        ...

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Return the memories that best match ``query``.

        Args:
            query (str): search query.
            limit (int): maximum number of items to return. Defaults to ``10``.

        Returns:
            list[MemoryEntry]: matches ordered by relevance (empty list when
                nothing matches).

        Note:
            Coroutine - must be awaited.
        """
        ...

    @abstractmethod
    async def update(self, memory_id: str, content: str) -> bool:
        """Replace the content of an existing memory.

        Args:
            memory_id (str): memory identifier.
            content (str): text content to process.

        Returns:
            bool: ``True`` when the entry existed and was updated.

        Note:
            Coroutine - must be awaited.
        """
        ...

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """Delete a memory entry.

        Args:
            memory_id (str): memory identifier.

        Returns:
            bool: ``True`` when an entry was removed.

        Note:
            Coroutine - must be awaited.
        """
        ...

    @abstractmethod
    async def list_all(self, limit: int = 100) -> list[MemoryEntry]:
        """Return the most recent memories.

        Args:
            limit (int): maximum number of items to return. Defaults to
                ``100``.

        Returns:
            list[MemoryEntry]: stored memories, newest first.

        Note:
            Coroutine - must be awaited.
        """
        ...

    @abstractmethod
    async def clear(self) -> None:
        """Remove every memory held by this backend.

        Note:
            Coroutine - must be awaited.
        """
        ...

    def calculate_importance(self, content: str, metadata: dict[str, Any]) -> float:
        """
        Calculate importance.

        Args:
            content (str): text content to process.
            metadata (dict[str, Any]): mapping of metadata.

        Returns:
            float: the computed numeric value.
        """
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
