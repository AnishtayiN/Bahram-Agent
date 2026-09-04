from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

class FileWriteSafety:

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
        self._safe_root = root

    def is_path_safe(self, path: str) -> tuple[bool, str]:
        path_str = str(path)
        has_parent_ref = ".." in Path(path_str).parts
        real_path = os.path.realpath(path_str)

        # Safe-root sandbox: every path must stay inside the configured root.
        if self._safe_root:
            root = os.path.realpath(self._safe_root)
            if real_path != root and not real_path.startswith(root + os.sep):
                return False, f"Path is outside safe root: {self._safe_root}"
        # Without a configured root, parent-directory traversal is only
        # allowed when the resolved destination still stays inside the
        # current working directory.
        elif has_parent_ref:
            cwd = os.path.realpath(os.getcwd())
            if real_path != cwd and not real_path.startswith(cwd + os.sep):
                return False, "Path traversal escapes working directory"

        for protected in self._protected_paths:
            protected_real = os.path.realpath(protected)
            if real_path == protected_real or real_path.startswith(protected_real + os.sep):
                return False, f"Path is protected: {protected}"

        if os.path.exists(path):
            size = os.path.getsize(path)
            if size > self._max_file_size:
                return False, f"File too large: {size} > {self._max_file_size}"

        return True, "OK"

    def check_write(self, path: str) -> tuple[bool, str]:
        return self.is_path_safe(path)

    def add_protected_path(self, path: str) -> None:
        if path not in self._protected_paths:
            self._protected_paths.append(path)

    def remove_protected_path(self, path: str) -> bool:
        if path in self._protected_paths:
            self._protected_paths.remove(path)
            return True
        return False

    def set_max_file_size(self, max_size: int) -> None:
        self._max_file_size = max_size
