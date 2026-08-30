from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

class FileWriteSafety:
    ""

    def __init__(self) -> None:
        self._protected_paths: list[str] = [
            "/etc/passwd",
            "/etc/shadow",
            "/etc/sudoers",
            "/boot",
            "/sys",
            "/proc",
            "/root/.ssh",
        ]
        self._safe_root: str = ""
        self._max_file_size: int = 100 * 1024 * 1024

    def set_safe_root(self, root: str) -> None:
        ""
        self._safe_root = root

    def is_path_safe(self, path: str) -> tuple[bool, str]:
        ""
        abs_path = os.path.abspath(path)

        for protected in self._protected_paths:
            if abs_path.startswith(protected):
                return False, f"Path is protected: {protected}"

        if self._safe_root:
            safe_root = os.path.abspath(self._safe_root)
            if not abs_path.startswith(safe_root):
                return False, f"Path is outside safe root: {safe_root}"

        if os.path.exists(path):
            size = os.path.getsize(path)
            if size > self._max_file_size:
                return False, f"File too large: {size} > {self._max_file_size}"

        return True, "OK"

    def check_write(self, path: str) -> tuple[bool, str]:
        ""
        return self.is_path_safe(path)

    def add_protected_path(self, path: str) -> None:
        ""
        if path not in self._protected_paths:
            self._protected_paths.append(path)

    def remove_protected_path(self, path: str) -> bool:
        ""
        if path in self._protected_paths:
            self._protected_paths.remove(path)
            return True
        return False

    def set_max_file_size(self, max_size: int) -> None:
        ""
        self._max_file_size = max_size
