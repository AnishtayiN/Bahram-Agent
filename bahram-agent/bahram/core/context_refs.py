"""Context references for Bahram Agent."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ContextReference:
    """A reference to context from another file/source."""

    id: str
    source: str  # file, url, skill
    path: str
    description: str = ""
    content: str = ""
    metadata: dict = field(default_factory=dict)


class ContextReferenceManager:
    """Manage context references."""

    def __init__(self) -> None:
        self._references: dict[str, ContextReference] = {}
        self._counter = 0

    def add_reference(
        self,
        source: str,
        path: str,
        description: str = "",
        content: str = "",
    ) -> ContextReference:
        """Add a context reference."""
        self._counter += 1
        ref = ContextReference(
            id=f"ref_{self._counter}",
            source=source,
            path=path,
            description=description,
            content=content,
        )
        self._references[ref.id] = ref
        return ref

    def remove_reference(self, ref_id: str) -> bool:
        """Remove a reference."""
        if ref_id in self._references:
            del self._references[ref_id]
            return True
        return False

    def get_reference(self, ref_id: str) -> Optional[ContextReference]:
        """Get a reference by ID."""
        return self._references.get(ref_id)

    def list_references(self) -> list[ContextReference]:
        """List all references."""
        return list(self._references.values())

    def resolve_references(self) -> str:
        """Resolve all references and return combined content."""
        parts = []
        for ref in self._references.values():
            if ref.content:
                parts.append(f"## {ref.description or ref.path}\n\n{ref.content}")
            elif ref.source == "file":
                try:
                    content = Path(ref.path).read_text(encoding="utf-8")
                    parts.append(f"## {ref.description or ref.path}\n\n{content}")
                except Exception as e:
                    logger.warning(f"Failed to read {ref.path}: {e}")
        return "\n\n---\n\n".join(parts)
