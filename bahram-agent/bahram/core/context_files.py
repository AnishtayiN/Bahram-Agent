"""
Context files.

Public objects: ``ContextFiles``.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ContextFiles:
    """
    Context files.
    """

    def __init__(self, workspace_root: str = ".") -> None:
        """
        Initialise a ContextFiles instance.

        Args:
            workspace_root (str): workspace root string. Defaults to ``'.'``.
        """
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
        """
        Load context.

        Returns:
            str: the rendered string.
        """
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
        """
        Return the loaded files.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        loaded = []
        for filename in self._context_files:
            file_path = self.workspace_root / filename
            if file_path.exists():
                loaded.append(filename)
        return loaded

    def add_context_file(self, filename: str) -> None:
        """
        Add context file.

        Args:
            filename (str): filename string.
        """
        if filename not in self._context_files:
            self._context_files.append(filename)

    def remove_context_file(self, filename: str) -> bool:
        """
        Remove context file.

        Args:
            filename (str): filename string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        if filename in self._context_files:
            self._context_files.remove(filename)
            return True
        return False

    def save_context(self, filename: str, content: str) -> bool:
        """
        Save context.

        Args:
            filename (str): filename string.
            content (str): text content to process.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        try:
            file_path = self.workspace_root / filename
            file_path.write_text(content)
            return True
        except Exception as e:
            logger.warning(f"Failed to save {filename}: {e}")
            return False
