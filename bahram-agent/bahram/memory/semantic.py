"""Semantic memory for storing facts and knowledge."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from bahram.memory.base import BaseMemory, MemoryEntry

logger = logging.getLogger(__name__)


class SemanticMemory(BaseMemory):
    """Memory system for storing facts and knowledge.

    Semantic memory stores structured knowledge about the world,
    concepts, and relationships. It's used for factual recall.
    """

    def __init__(self, storage_path: str = "data/semantic.json") -> None:
        self.storage_path = Path(storage_path)
        self._memories: dict[str, MemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load semantic memories from disk."""
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
                logger.error(f"Failed to load semantic memories: {e}")

    def _save(self) -> None:
        """Save semantic memories to disk."""
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
            logger.error(f"Failed to save semantic memories: {e}")

    async def add(self, content: str, metadata: Optional[dict[str, Any]] = None) -> str:
        """Add a semantic memory."""
        import uuid

        memory_id = str(uuid.uuid4())
        metadata = metadata or {}

        # Add category if not present
        if "category" not in metadata:
            metadata["category"] = self._categorize(content)

        entry = MemoryEntry(
            id=memory_id,
            content=content,
            metadata=metadata,
            importance=self.calculate_importance(content, metadata),
        )
        self._memories[memory_id] = entry
        self._save()
        return memory_id

    async def get(self, memory_id: str) -> Optional[MemoryEntry]:
        """Get a semantic memory by ID."""
        entry = self._memories.get(memory_id)
        if entry:
            entry.access_count += 1
            entry.last_accessed = datetime.now()
        return entry

    async def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Search semantic memories by content."""
        query_lower = query.lower()
        results = []

        for entry in self._memories.values():
            if query_lower in entry.content.lower():
                results.append(entry)

        # Sort by importance
        results.sort(key=lambda x: x.importance, reverse=True)
        return results[:limit]

    async def update(self, memory_id: str, content: str) -> bool:
        """Update a semantic memory."""
        if memory_id in self._memories:
            self._memories[memory_id].content = content
            self._save()
            return True
        return False

    async def delete(self, memory_id: str) -> bool:
        """Delete a semantic memory."""
        if memory_id in self._memories:
            del self._memories[memory_id]
            self._save()
            return True
        return False

    async def list_all(self, limit: int = 100) -> list[MemoryEntry]:
        """List all semantic memories."""
        entries = list(self._memories.values())
        entries.sort(key=lambda x: x.importance, reverse=True)
        return entries[:limit]

    async def clear(self) -> None:
        """Clear all semantic memories."""
        self._memories.clear()
        self._save()

    async def add_fact(self, fact: str, category: str = "general") -> str:
        """Add a fact to memory."""
        return await self.add(fact, {"type": "fact", "category": category})

    async def add_concept(self, concept: str, definition: str) -> str:
        """Add a concept to memory."""
        content = f"{concept}: {definition}"
        return await self.add(content, {"type": "concept", "concept": concept})

    async def add_relationship(
        self, subject: str, predicate: str, obj: str
    ) -> str:
        """Add a relationship to memory."""
        content = f"{subject} {predicate} {obj}"
        return await self.add(
            content,
            {"type": "relationship", "subject": subject, "object": obj},
        )

    async def get_by_category(self, category: str) -> list[MemoryEntry]:
        """Get memories by category."""
        return [
            m
            for m in self._memories.values()
            if m.metadata.get("category") == category
        ]

    async def get_facts(self) -> list[MemoryEntry]:
        """Get all facts."""
        return [m for m in self._memories.values() if m.metadata.get("type") == "fact"]

    async def get_concepts(self) -> list[MemoryEntry]:
        """Get all concepts."""
        return [
            m for m in self._memories.values() if m.metadata.get("type") == "concept"
        ]

    def _categorize(self, content: str) -> str:
        """Categorize content based on keywords."""
        content_lower = content.lower()

        if any(kw in content_lower for kw in ["function", "class", "import", "def"]):
            return "code"
        elif any(kw in content_lower for kw in ["error", "bug", "fix", "issue"]):
            return "debugging"
        elif any(kw in content_lower for kw in ["install", "setup", "config"]):
            return "configuration"
        elif any(kw in content_lower for kw in ["api", "endpoint", "request"]):
            return "api"
        elif any(kw in content_lower for kw in ["user", "preference", "setting"]):
            return "preferences"
        else:
            return "general"
