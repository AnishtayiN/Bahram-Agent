"""Personality/SOUL.md system for Bahram Agent."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Personality:
    """Load and manage agent personality from SOUL.md."""

    def __init__(self, workspace_root: str = ".") -> None:
        self.workspace_root = Path(workspace_root)
        self._soul_content: str = ""
        self._loaded = False

    def load(self) -> None:
        """Load SOUL.md from workspace."""
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
        """Get personality content."""
        self.load()
        return self._soul_content

    def get_system_prompt_addition(self) -> str:
        """Get personality as system prompt addition."""
        personality = self.get_personality()
        if not personality:
            return ""

        return f"\n\n## Your Personality\n{personality}"

    def set_personality(self, content: str) -> None:
        """Set personality content."""
        self._soul_content = content
        self._save()

    def _save(self) -> None:
        """Save personality to SOUL.md."""
        soul_file = self.workspace_root / "SOUL.md"
        try:
            soul_file.write_text(self._soul_content)
        except Exception as e:
            logger.warning(f"Failed to save SOUL.md: {e}")

    def has_personality(self) -> bool:
        """Check if personality is loaded."""
        self.load()
        return bool(self._soul_content)
