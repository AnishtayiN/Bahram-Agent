"""
Conversation.

Public objects: ``ConversationMemory``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from bahram.memory.base import BaseMemory, MemoryEntry

logger = logging.getLogger(__name__)


class ConversationMemory(BaseMemory):
    """
    Conversation memory.
    """

    def __init__(self, storage_path: str = "data/conversations.json") -> None:
        """
        Initialise a ConversationMemory instance.

        Args:
            storage_path (str): storage path string. Defaults to ``'data/conversations.json'``.
        """
        self.storage_path = Path(storage_path)
        self._memories: dict[str, MemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
                    for item in data:
                        entry = MemoryEntry(
                            id=item["id"],
                            content=item["content"],
                            timestamp=datetime.fromisoformat(item["timestamp"]),
                            metadata=item.get("metadata", {}),
                            importance=item.get("importance", 0.5),
                            access_count=item.get("access_count", 0),
                        )
                        self._memories[entry.id] = entry
            except Exception as e:
                logger.error(f"Failed to load memories: {e}")

    def _save(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = [
                {
                    "id": m.id,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "metadata": m.metadata,
                    "importance": m.importance,
                    "access_count": m.access_count,
                }
                for m in self._memories.values()
            ]
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save memories: {e}")

    async def add(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        """
        Add.

        Args:
            content (str): text content to process.
            metadata (dict[str, Any] | None): mapping of metadata. Defaults to ``None``.

        Returns:
            str: the rendered string.

        Note:
            Coroutine - must be awaited.
        """
        import uuid

        memory_id = str(uuid.uuid4())
        entry = MemoryEntry(
            id=memory_id,
            content=content,
            metadata=metadata or {},
            importance=self.calculate_importance(content, metadata or {}),
        )
        self._memories[memory_id] = entry
        self._save()
        return memory_id

    async def get(self, memory_id: str) -> MemoryEntry | None:
        """
        Get.

        Args:
            memory_id (str): memory id string.

        Returns:
            MemoryEntry | None: the resulting object, or ``None`` when it is not available.

        Note:
            Coroutine - must be awaited.
        """
        entry = self._memories.get(memory_id)
        if entry:
            entry.access_count += 1
            entry.last_accessed = datetime.now()
        return entry

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """
        Search.

        Args:
            query (str): search query.
            limit (int): maximum number of items to return. Defaults to ``10``.

        Returns:
            list[MemoryEntry]: a sequence of MemoryEntry entries (empty when there is nothing to
                report).

        Note:
            Coroutine - must be awaited.
        """
        query_lower = query.lower()
        results = []

        for entry in self._memories.values():
            if query_lower in entry.content.lower():
                results.append(entry)

        results.sort(key=lambda x: (x.importance, x.timestamp), reverse=True)
        return results[:limit]

    async def update(self, memory_id: str, content: str) -> bool:
        """
        Update.

        Args:
            memory_id (str): memory id string.
            content (str): text content to process.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        if memory_id in self._memories:
            self._memories[memory_id].content = content
            self._save()
            return True
        return False

    async def delete(self, memory_id: str) -> bool:
        """
        Delete.

        Args:
            memory_id (str): memory id string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        if memory_id in self._memories:
            del self._memories[memory_id]
            self._save()
            return True
        return False

    async def list_all(self, limit: int = 100) -> list[MemoryEntry]:
        """
        List all.

        Args:
            limit (int): maximum number of items to return. Defaults to ``100``.

        Returns:
            list[MemoryEntry]: a sequence of MemoryEntry entries (empty when there is nothing to
                report).

        Note:
            Coroutine - must be awaited.
        """
        entries = list(self._memories.values())
        entries.sort(key=lambda x: x.timestamp, reverse=True)
        return entries[:limit]

    async def clear(self) -> None:
        """
        Clear.

        Note:
            Coroutine - must be awaited.
        """
        self._memories.clear()
        self._save()

    async def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        """
        Return the recent.

        Args:
            limit (int): maximum number of items to return. Defaults to ``10``.

        Returns:
            list[MemoryEntry]: a sequence of MemoryEntry entries (empty when there is nothing to
                report).

        Note:
            Coroutine - must be awaited.
        """
        entries = list(self._memories.values())
        entries.sort(key=lambda x: x.timestamp, reverse=True)
        return entries[:limit]

    async def get_important(self, limit: int = 10) -> list[MemoryEntry]:
        """
        Return the important.

        Args:
            limit (int): maximum number of items to return. Defaults to ``10``.

        Returns:
            list[MemoryEntry]: a sequence of MemoryEntry entries (empty when there is nothing to
                report).

        Note:
            Coroutine - must be awaited.
        """
        entries = list(self._memories.values())
        entries.sort(key=lambda x: x.importance, reverse=True)
        return entries[:limit]
