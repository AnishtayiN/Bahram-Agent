"""Intelligent Memory Search with Semantic Understanding."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MemoryResult:
    """A memory search result."""

    id: str
    content: str
    score: float
    source: str
    timestamp: float
    metadata: dict = field(default_factory=dict)


class SemanticMemory:
    """Semantic memory search and retrieval."""

    def __init__(self, data_dir: str = "data/memory") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._memories: list[dict] = []
        self._load()

    def _load(self) -> None:
        """Load memories from disk."""
        memories_file = self.data_dir / "semantic_memory.json"
        if memories_file.exists():
            try:
                with open(memories_file) as f:
                    self._memories = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load memories: {e}")

    def _save(self) -> None:
        """Save memories to disk."""
        memories_file = self.data_dir / "semantic_memory.json"
        with open(memories_file, "w") as f:
            json.dump(self._memories, f, indent=2)

    def add(
        self,
        content: str,
        source: str = "",
        metadata: dict = None,
    ) -> str:
        """Add a memory."""
        import uuid

        memory_id = str(uuid.uuid4())[:12]
        self._memories.append({
            "id": memory_id,
            "content": content,
            "source": source,
            "timestamp": time.time(),
            "metadata": metadata or {},
        })
        self._save()
        return memory_id

    def search(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[MemoryResult]:
        """Search memories semantically."""
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for memory in self._memories:
            content = memory.get("content", "")
            content_lower = content.lower()
            content_words = set(content_lower.split())

            # Calculate similarity score
            score = 0.0

            # Exact match
            if query_lower in content_lower:
                score += 1.0

            # Word overlap
            if query_words:
                overlap = len(query_words & content_words) / len(query_words)
                score += overlap * 0.5

            # Position bonus (earlier matches score higher)
            position = content_lower.find(query_lower)
            if position >= 0:
                score += 0.3 * (1 - position / max(len(content_lower), 1))

            if score >= min_score:
                results.append(MemoryResult(
                    id=memory["id"],
                    content=content,
                    score=score,
                    source=memory.get("source", ""),
                    timestamp=memory.get("timestamp", 0),
                    metadata=memory.get("metadata", {}),
                ))

        # Sort by score
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def get(self, memory_id: str) -> Optional[dict]:
        """Get a memory by ID."""
        for memory in self._memories:
            if memory["id"] == memory_id:
                return memory
        return None

    def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        for i, memory in enumerate(self._memories):
            if memory["id"] == memory_id:
                del self._memories[i]
                self._save()
                return True
        return False

    def get_context(self, query: str, max_memories: int = 5) -> str:
        """Get relevant context for a query."""
        results = self.search(query, limit=max_memories)
        if not results:
            return ""

        context_parts = []
        for r in results:
            context_parts.append(f"[{r.source}] {r.content[:200]}")

        return "\n".join(context_parts)

    def get_statistics(self) -> dict[str, Any]:
        """Get memory statistics."""
        return {
            "total_memories": len(self._memories),
            "sources": list(set(m.get("source", "") for m in self._memories)),
        }
