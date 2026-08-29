"""Memory providers for Bahram Agent."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


class MemoryProviderType(str, Enum):
    """Memory provider types."""

    LOCAL = "local"
    QDRANT = "qdrant"
    PINECONE = "pinecone"
    WEAVIATE = "weaviate"
    REDIS = "redis"


@dataclass
class MemoryEntry:
    """A memory entry."""

    id: str
    content: str
    metadata: dict = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list)
    timestamp: float = 0.0


class MemoryProvider:
    """Base memory provider."""

    def __init__(self, provider_type: MemoryProviderType) -> None:
        self.provider_type = provider_type

    async def add(self, entry: MemoryEntry) -> bool:
        """Add a memory entry."""
        raise NotImplementedError

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Search memory entries."""
        raise NotImplementedError

    async def delete(self, entry_id: str) -> bool:
        """Delete a memory entry."""
        raise NotImplementedError

    async def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """Get a memory entry by ID."""
        raise NotImplementedError

    async def count(self) -> int:
        """Count total entries."""
        raise NotImplementedError


class LocalMemoryProvider(MemoryProvider):
    """Local filesystem memory provider."""

    def __init__(self, data_dir: str = "data/memory") -> None:
        super().__init__(MemoryProviderType.LOCAL)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, MemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load entries from disk."""
        entries_file = self.data_dir / "local_memory.json"
        if entries_file.exists():
            try:
                with open(entries_file) as f:
                    data = json.load(f)
                for entry_data in data:
                    entry = MemoryEntry(**entry_data)
                    self._entries[entry.id] = entry
            except Exception as e:
                logger.warning(f"Failed to load local memory: {e}")

    def _save(self) -> None:
        """Save entries to disk."""
        entries_file = self.data_dir / "local_memory.json"
        data = [
            {
                "id": e.id,
                "content": e.content,
                "metadata": e.metadata,
                "embedding": e.embedding,
                "timestamp": e.timestamp,
            }
            for e in self._entries.values()
        ]
        with open(entries_file, "w") as f:
            json.dump(data, f, indent=2)

    async def add(self, entry: MemoryEntry) -> bool:
        """Add a memory entry."""
        if not entry.timestamp:
            entry.timestamp = time.time()
        self._entries[entry.id] = entry
        self._save()
        return True

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Search memory entries (simple text matching)."""
        results = []
        query_lower = query.lower()

        for entry in self._entries.values():
            if query_lower in entry.content.lower():
                results.append(entry)

        # Sort by timestamp (newest first)
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results[:limit]

    async def delete(self, entry_id: str) -> bool:
        """Delete a memory entry."""
        if entry_id in self._entries:
            del self._entries[entry_id]
            self._save()
            return True
        return False

    async def get(self, entry_id: str) -> Optional[MemoryEntry]:
        """Get a memory entry by ID."""
        return self._entries.get(entry_id)

    async def count(self) -> int:
        """Count total entries."""
        return len(self._entries)


class MemoryProviderManager:
    """Manage memory providers."""

    def __init__(self, data_dir: str = "data/memory") -> None:
        self.data_dir = data_dir
        self._providers: dict[str, MemoryProvider] = {}
        self._active_provider: str = "local"

        # Register local provider
        self._providers["local"] = LocalMemoryProvider(data_dir)

    def get_provider(self, name: str = None) -> MemoryProvider:
        """Get a provider."""
        return self._providers.get(name or self._active_provider, self._providers["local"])

    def set_active_provider(self, name: str) -> bool:
        """Set active provider."""
        if name in self._providers:
            self._active_provider = name
            return True
        return False

    def register_provider(self, name: str, provider: MemoryProvider) -> None:
        """Register a new provider."""
        self._providers[name] = provider

    def list_providers(self) -> list[dict]:
        """List available providers."""
        return [
            {
                "name": name,
                "type": provider.provider_type.value,
                "is_active": name == self._active_provider,
            }
            for name, provider in self._providers.items()
        ]
