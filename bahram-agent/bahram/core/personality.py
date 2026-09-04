"""
Personality.

Public objects: ``Personality``.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Personality:
    """
    Personality.
    """

    def __init__(self, workspace_root: str = ".") -> None:
        """
        Initialise a Personality instance.

        Args:
            workspace_root (str): workspace root string. Defaults to ``'.'``.
        """
        self.workspace_root = Path(workspace_root)
        self._soul_content: str = ""
        self._loaded = False

    def load(self) -> None:
        """
        Load.
        """
        if self._loaded:
            return

        soul_file = self.workspace_root / "SOUL.md"
        if soul_file.exists():
            try:
                self._soul_content = soul_file.read_text()
                logger.info("Loaded SOUL.md personality")
            except Exception as e:
                logger.warning(f"Failed to load SOUL.md: {e}")

        self._loaded = True

    def get_personality(self) -> str:
        """
        Return the personality.

        Returns:
            str: the rendered string.
        """
        self.load()
        return self._soul_content

    def get_system_prompt_addition(self) -> str:
        """
        Return the system prompt addition.

        Returns:
            str: the rendered string.
        """
        personality = self.get_personality()
        if not personality:
            return ""

        return f"\n\n## Your Personality\n{personality}"

    def set_personality(self, content: str) -> None:
        """
        Set the personality.

        Args:
            content (str): text content to process.
        """
        self._soul_content = content
        self._save()

    def _save(self) -> None:
        soul_file = self.workspace_root / "SOUL.md"
        try:
            soul_file.write_text(self._soul_content)
        except Exception as e:
            logger.warning(f"Failed to save SOUL.md: {e}")

    def has_personality(self) -> bool:
        """
        Return ``True`` when the object has personality.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        self.load()
        return bool(self._soul_content)
