"""File write safety for Bahram Agent."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# Protected paths that are always blocked
PROTECTED_PATHS = [
    "~/.ssh/",
    "~/.aws/",
    "~/.kube/",
    "/etc/sudoers",
    "~/.netrc",
    "auth.json",
    ".env",
    ".env.local",
    ".env.production",
    ".envrc",
    ".anthropic_oauth.json",
    "mcp-tokens/",
    "pairing/",
]


class FileWriteSafety:
    """Enforce file write safety rules."""

    def __init__(self, safe_root: str = "") -> None:
        self.safe_root = safe_root
        self._deny_patterns: list[str] = []

    def check_write(self, path: str) -> tuple[bool, str]:
        """Check if a file write is allowed.

        Returns:
            Tuple of (is_allowed, reason)
        """
        expanded = os.path.expanduser(path)
        normalized = os.path.normpath(expanded)

        # Check protected paths
        for protected in PROTECTED_PATHS:
            protected_expanded = os.path.expanduser(protected)
            if normalized.startswith(protected_expanded):
                return False, f"Protected path: {protected}"

        # Check safe root
        if self.safe_root:
            safe_root_expanded = os.path.expanduser(self.safe_root)
            if not normalized.startswith(safe_root_expanded):
                return False, f"Outside safe root: {self.safe_root}"

        # Check deny patterns
        for pattern in self._deny_patterns:
            if pattern in normalized:
                return False, f"Denied by pattern: {pattern}"

        return True, ""

    def set_safe_root(self, root: str) -> None:
        """Set the safe root directory."""
        self.safe_root = root

    def add_deny_pattern(self, pattern: str) -> None:
        """Add a deny pattern."""
        if pattern not in self._deny_patterns:
            self._deny_patterns.append(pattern)

    def remove_deny_pattern(self, pattern: str) -> bool:
        """Remove a deny pattern."""
        if pattern in self._deny_patterns:
            self._deny_patterns.remove(pattern)
            return True
        return False

    @classmethod
    def from_env(cls) -> "FileWriteSafety":
        """Create from environment variable."""
        safe_root = os.environ.get("HERMES_WRITE_SAFE_ROOT", "")
        return cls(safe_root=safe_root)
