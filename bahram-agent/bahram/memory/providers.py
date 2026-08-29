"""External memory providers for Bahram Agent."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MemoryProvider(ABC):
    """Base class for memory providers."""

    @abstractmethod
    async def store(self, key: str, value: str, metadata: dict = None) -> bool:
        """Store a memory."""
        pass

    @abstractmethod
    async def retrieve(self, key: str) -> Optional[str]:
        """Retrieve a memory."""
        pass

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search memories."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete a memory."""
        pass


class InMemoryProvider(MemoryProvider):
    """Simple in-memory provider."""

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}

    async def store(self, key: str, value: str, metadata: dict = None) -> bool:
        self._store[key] = {"value": value, "metadata": metadata or {}}
        return True

    async def retrieve(self, key: str) -> Optional[str]:
        entry = self._store.get(key)
        return entry["value"] if entry else None

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        results = []
        query_lower = query.lower()
        for key, entry in self._store.items():
            if query_lower in entry["value"].lower() or query_lower in key.lower():
                results.append({"key": key, "value": entry["value"]})
        return results[:limit]

    async def delete(self, key: str) -> bool:
        if key in self._store:
            del self._store[key]
            return True
        return False


class HonchoProvider(MemoryProvider):
    """Honcho dialectic memory provider."""

    def __init__(self, api_key: str = "", app_id: str = "") -> None:
        self.api_key = api_key
        self.app_id = app_id

    async def store(self, key: str, value: str, metadata: dict = None) -> bool:
        logger.info(f"Honcho store: {key}")
        return True

    async def retrieve(self, key: str) -> Optional[str]:
        return None

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        return []

    async def delete(self, key: str) -> bool:
        return True


class Mem0Provider(MemoryProvider):
    """Mem0 memory provider."""

    def __init__(self, api_key: str = "") -> None:
        self.api_key = api_key

    async def store(self, key: str, value: str, metadata: dict = None) -> bool:
        logger.info(f"Mem0 store: {key}")
        return True

    async def retrieve(self, key: str) -> Optional[str]:
        return None

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        return []

    async def delete(self, key: str) -> bool:
        return True


class MemoryProviderManager:
    """Manage memory providers."""

    def __init__(self) -> None:
        self._providers: dict[str, MemoryProvider] = {
            "in_memory": InMemoryProvider(),
        }
        self._active: str = "in_memory"

    def register_provider(self, name: str, provider: MemoryProvider) -> None:
        """Register a memory provider."""
        self._providers[name] = provider

    def set_active(self, name: str) -> bool:
        """Set the active provider."""
        if name in self._providers:
            self._active = name
            return True
        return False

    def get_active(self) -> MemoryProvider:
        """Get the active provider."""
        return self._providers[self._active]

    def list_providers(self) -> list[str]:
        """List available providers."""
        return list(self._providers.keys())
