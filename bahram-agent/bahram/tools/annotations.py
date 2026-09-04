from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class ToolAnnotation:

    key: str
    value: Any
    timestamp: float = 0.0
    metadata: dict = field(default_factory=dict)

class AnnotationManager:

    def __init__(self) -> None:
        self._annotations: dict[str, list[ToolAnnotation]] = {}

    def add_annotation(
        self,
        tool_call_id: str,
        key: str,
        value: Any,
        metadata: dict = None,
    ) -> None:
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
        annotations = self._annotations.get(tool_call_id, [])
        return [
            {
                "key": a.key,
                "value": a.value,
                "timestamp": a.timestamp,
            }
            for a in annotations
        ]

    def get_annotation(self, tool_call_id: str, key: str) -> Optional[Any]:
        annotations = self._annotations.get(tool_call_id, [])
        for a in annotations:
            if a.key == key:
                return a.value
        return None

    def clear_annotations(self, tool_call_id: str) -> None:
        self._annotations.pop(tool_call_id, None)

    def get_all_annotations(self) -> dict[str, list[dict]]:
        return {
            k: self.get_annotations(k)
            for k in self._annotations.keys()
        }

    def set_exit_code(self, tool_call_id: str, exit_code: int) -> None:
        self.add_annotation(tool_call_id, "exit_code", exit_code)

    def set_utf16_transcoded(self, tool_call_id: str, transcoded: bool) -> None:
        self.add_annotation(tool_call_id, "utf16_transcoded", transcoded)

    def set_output_size(self, tool_call_id: str, size: int) -> None:
        self.add_annotation(tool_call_id, "output_size", size)
