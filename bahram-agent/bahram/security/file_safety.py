"""
File safety.

Public objects: ``FileWriteSafety``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class FileWriteSafety:
    """
    File write safety.
    """

    def __init__(self) -> None:
        """
        Initialise a FileWriteSafety instance.
        """
        # Directories, not just individual files: /etc/nginx/nginx.conf and
        # /etc/cron.d/payload are every bit as dangerous as /etc/passwd, and
        # enumerating files one by one can never keep up.
        self._protected_paths: list[str] = [
            "/etc",
            "/boot",
            "/sys",
            "/proc",
            "/dev",
            "/bin",
            "/sbin",
            "/usr/bin",
            "/usr/sbin",
            "/root",
        ]
        self._safe_root: str = ""
        self._max_file_size: int = 100 * 1024 * 1024

    def set_safe_root(self, root: str) -> None:
        """
        Set the safe root.

        Args:
            root (str): root string.
        """
        self._safe_root = root

    def is_path_safe(self, path: str) -> tuple[bool, str]:
        """
        Return ``True`` when path safe.

        Args:
            path (str): filesystem path to operate on.

        Returns:
            tuple[bool, str]: a sequence of bool, str entries (empty when there is nothing to
                report).
        """
        path_str = str(path)
        has_parent_ref = ".." in Path(path_str).parts
        real_path = os.path.realpath(path_str)
        absolute_path = os.path.abspath(path_str)

        # Safe-root sandbox: every path must stay inside the configured root.
        if self._safe_root:
            root = os.path.realpath(self._safe_root)
            if real_path != root and not real_path.startswith(root + os.sep):
                return False, f"Path is outside safe root: {self._safe_root}"
        # Without a configured root, the destination must still land inside the
        # current working directory whenever anything redirects it there: an
        # explicit "..", or a symlink.  A symlink is the quieter of the two -
        # the path can contain no ".." at all and still resolve somewhere else
        # entirely, which is why resolving the path is not optional here.
        else:
            cwd = os.path.realpath(os.getcwd())
            inside_cwd = real_path == cwd or real_path.startswith(cwd + os.sep)
            redirected = has_parent_ref or real_path != absolute_path
            if redirected and not inside_cwd:
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
        """
        Check write.

        Args:
            path (str): filesystem path to operate on.

        Returns:
            tuple[bool, str]: a sequence of bool, str entries (empty when there is nothing to
                report).
        """
        return self.is_path_safe(path)

    def add_protected_path(self, path: str) -> None:
        """
        Add protected path.

        Args:
            path (str): filesystem path to operate on.
        """
        if path not in self._protected_paths:
            self._protected_paths.append(path)

    def remove_protected_path(self, path: str) -> bool:
        """
        Remove protected path.

        Args:
            path (str): filesystem path to operate on.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        if path in self._protected_paths:
            self._protected_paths.remove(path)
            return True
        return False

    def set_max_file_size(self, max_size: int) -> None:
        """
        Set the max file size.

        Args:
            max_size (int): numeric value for max size.
        """
        self._max_file_size = max_size
