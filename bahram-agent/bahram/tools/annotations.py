"""
Annotations.

Public objects: ``ToolAnnotation``, ``AnnotationManager``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolAnnotation:
    """
    Tool annotation.

    Attributes:
        key (str): key string.
        value (Any): value.
        timestamp (float): numeric value for timestamp.
        metadata (dict): mapping of metadata.
    """

    key: str
    value: Any
    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)


class AnnotationManager:
    """
    Annotation manager.
    """

    def __init__(self) -> None:
        """
        Initialise a AnnotationManager instance.
        """
        self._annotations: dict[str, list[ToolAnnotation]] = {}

    def add_annotation(
        self,
        tool_call_id: str,
        key: str,
        value: Any,
        metadata: dict = None,
    ) -> None:
        """
        Add annotation.

        Args:
            tool_call_id (str): tool call id string.
            key (str): key string.
            value (Any): value.
            metadata (dict): mapping of metadata. Defaults to ``None``.
        """
        import time

        if tool_call_id not in self._annotations:
            self._annotations[tool_call_id] = []

        self._annotations[tool_call_id].append(
            ToolAnnotation(
                key=key,
                value=value,
                timestamp=time.time(),
                metadata=metadata or {},
            )
        )

    def get_annotations(self, tool_call_id: str) -> list[dict]:
        """
        Return the annotations.

        Args:
            tool_call_id (str): tool call id string.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        annotations = self._annotations.get(tool_call_id, [])
        return [
            {
                "key": a.key,
                "value": a.value,
                "timestamp": a.timestamp,
            }
            for a in annotations
        ]

    def get_annotation(self, tool_call_id: str, key: str) -> Any | None:
        """Return the *most recent* annotation recorded for ``key``.

        Annotations are append-only, so ``set_exit_code``/``set_output_size``
        may store several values for the same key.  Callers read the value
        they last wrote, therefore the newest entry wins.  The previous
        implementation returned the oldest, which meant a re-annotated
        ``exit_code`` would keep reporting the first (stale) value.

        Args:
            tool_call_id (str): tool call id string.
            key (str): key string.

        Returns:
            Any | None: the newest value, or ``None`` when the key is absent.
        """
        annotations = self._annotations.get(tool_call_id, [])
        for a in reversed(annotations):
            if a.key == key:
                return a.value
        return None

    def clear_annotations(self, tool_call_id: str) -> None:
        """
        Clear annotations.

        Args:
            tool_call_id (str): tool call id string.
        """
        self._annotations.pop(tool_call_id, None)

    def get_all_annotations(self) -> dict[str, list[dict]]:
        """
        Return the all annotations.

        Returns:
            dict[str, list[dict]]: a mapping of str, list[dict].
        """
        return {k: self.get_annotations(k) for k in self._annotations.keys()}

    def set_exit_code(self, tool_call_id: str, exit_code: int) -> None:
        """
        Set the exit code.

        Args:
            tool_call_id (str): tool call id string.
            exit_code (int): numeric value for exit code.
        """
        self.add_annotation(tool_call_id, "exit_code", exit_code)

    def set_utf16_transcoded(self, tool_call_id: str, transcoded: bool) -> None:
        """
        Set the utf 16 transcoded.

        Args:
            tool_call_id (str): tool call id string.
            transcoded (bool): when ``True``, enable transcoded.
        """
        self.add_annotation(tool_call_id, "utf16_transcoded", transcoded)

    def set_output_size(self, tool_call_id: str, size: int) -> None:
        """
        Set the output size.

        Args:
            tool_call_id (str): tool call id string.
            size (int): numeric value for size.
        """
        self.add_annotation(tool_call_id, "output_size", size)
