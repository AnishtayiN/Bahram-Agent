"""Context files for Bahram Agent."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ContextFiles:
    """Load context from files in workspace."""

    def __init__(self, workspace_root: str = ".") -> None:
        self.workspace_root = Path(workspace_root)
        self._context_files: list[str] = [
            "CLAUDE.md",
            ".cursorrules",
            "AGENTS.md",
            "SOUL.md",
            ".github/copilot-instructions.md",
            "RULES.md",
        ]

    def load_context(self) -> str:
        """Load context from workspace files."""
        context_parts = []

        for filename in self._context_files:
            file_path = self.workspace_root / filename
            if file_path.exists():
                try:
                    content = file_path.read_text()
                    context_parts.append(f"=== {filename} ===\n{content}")
                except Exception as e:
                    logger.warning(f"Failed to load {filename}: {e}")

        return "\n\n".join(context_parts)

    def get_loaded_files(self) -> list[str]:
        """Get list of loaded context files."""
        loaded = []
        for filename in self._context_files:
            file_path = self.workspace_root / filename
            if file_path.exists():
                loaded.append(filename)
        return loaded

    def add_context_file(self, filename: str) -> None:
        """Add a context file to load."""
        if filename not in self._context_files:
            self._context_files.append(filename)

    def remove_context_file(self, filename: str) -> bool:
        """Remove a context file."""
        if filename in self._context_files:
            self._context_files.remove(filename)
            return True
        return False

    def save_context(self, filename: str, content: str) -> bool:
        """Save context to a file."""
        try:
            file_path = self.workspace_root / filename
            file_path.write_text(content)
            return True
        except Exception as e:
            logger.warning(f"Failed to save {filename}: {e}")
            return False
