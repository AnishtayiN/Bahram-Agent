"""
Context refs.

Public objects: ``ContextRef``, ``ContextRefs``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ContextRef:
    """
    Context ref.

    Attributes:
        id (str): id string.
        content (str): text content to process.
        source (str): source string.
        metadata (dict): mapping of metadata.
    """

    id: str
    content: str
    source: str
    metadata: dict = field(default_factory=dict)


class ContextRefs:
    """
    Context refs.
    """

    def __init__(self, data_dir: str = "data/context") -> None:
        """
        Initialise a ContextRefs instance.

        Args:
            data_dir (str): directory that holds the on-disk state. Defaults to ``'data/context'``.
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._refs: dict[str, ContextRef] = {}
        self._load()

    def _load(self) -> None:
        refs_file = self.data_dir / "context_refs.json"
        if refs_file.exists():
            try:
                with open(refs_file) as f:
                    data = json.load(f)
                for ref_data in data:
                    ref = ContextRef(**ref_data)
                    self._refs[ref.id] = ref
            except Exception as e:
                logger.warning(f"Failed to load context refs: {e}")

    def _save(self) -> None:
        refs_file = self.data_dir / "context_refs.json"
        data = [
            {
                "id": r.id,
                "content": r.content,
                "source": r.source,
                "metadata": r.metadata,
            }
            for r in self._refs.values()
        ]
        with open(refs_file, "w") as f:
            json.dump(data, f, indent=2)

    def add_ref(self, content: str, source: str = "", metadata: dict = None) -> ContextRef:
        """
        Add ref.

        Args:
            content (str): text content to process.
            source (str): source string. Defaults to ``''``.
            metadata (dict): mapping of metadata. Defaults to ``None``.

        Returns:
            ContextRef: the resulting ContextRef.
        """
        import hashlib
        import time

        ref_id = hashlib.md5(f"{content}{time.time()}".encode()).hexdigest()[:12]
        ref = ContextRef(
            id=ref_id,
            content=content,
            source=source,
            metadata=metadata or {},
        )
        self._refs[ref_id] = ref
        self._save()
        return ref

    def get_ref(self, ref_id: str) -> ContextRef | None:
        """
        Return the ref.

        Args:
            ref_id (str): ref id string.

        Returns:
            ContextRef | None: the resulting object, or ``None`` when it is not available.
        """
        return self._refs.get(ref_id)

    def search_refs(self, query: str) -> list[ContextRef]:
        """
        Search refs.

        Args:
            query (str): search query.

        Returns:
            list[ContextRef]: a sequence of ContextRef entries (empty when there is nothing to
                report).
        """
        query_lower = query.lower()
        results = []
        for ref in self._refs.values():
            if query_lower in ref.content.lower() or query_lower in ref.source.lower():
                results.append(ref)
        return results

    def delete_ref(self, ref_id: str) -> bool:
        """
        Delete ref.

        Args:
            ref_id (str): ref id string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        if ref_id in self._refs:
            del self._refs[ref_id]
            self._save()
            return True
        return False

    def get_context_for_message(self, message: str, max_refs: int = 5) -> str:
        """
        Return the context for message.

        Args:
            message (str): message to process.
            max_refs (int): numeric value for max refs. Defaults to ``5``.

        Returns:
            str: the rendered string.
        """
        refs = self.search_refs(message)[:max_refs]
        if not refs:
            return ""

        context_parts = []
        for ref in refs:
            context_parts.append(f"[{ref.source}] {ref.content[:200]}")

        return "\n".join(context_parts)

    def list_refs(self) -> list[dict]:
        """
        List refs.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        return [
            {
                "id": r.id,
                "source": r.source,
                "content_preview": r.content[:100],
            }
            for r in self._refs.values()
        ]
