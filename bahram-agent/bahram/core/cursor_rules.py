"""Cursor rules integration for Bahram Agent."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CursorRules:
    """Load and apply .cursorrules files."""

    def __init__(self, project_root: str = ".") -> None:
        self.project_root = Path(project_root)
        self._rules: list[str] = []
        self._loaded = False

    def load(self) -> None:
        """Load .cursorrules from project root."""
        if self._loaded:
            return

        rules_file = self.project_root / ".cursorrules"
        if rules_file.exists():
            try:
                content = rules_file.read_text()
                self._rules = [line.strip() for line in content.split("\n") if line.strip()]
                logger.info(f"Loaded {len(self._rules)} cursor rules")
            except Exception as e:
                logger.warning(f"Failed to load .cursorrules: {e}")

        self._loaded = True

    def get_rules(self) -> list[str]:
        """Get loaded rules."""
        self.load()
        return self._rules.copy()

    def get_rules_text(self) -> str:
        """Get rules as formatted text."""
        rules = self.get_rules()
        if not rules:
            return ""

        lines = ["## Cursor Rules", ""]
        for rule in rules:
            lines.append(f"- {rule}")
        return "\n".join(lines)

    def add_rule(self, rule: str) -> None:
        """Add a rule."""
        self.load()
        if rule not in self._rules:
            self._rules.append(rule)
            self._save()

    def remove_rule(self, rule: str) -> bool:
        """Remove a rule."""
        self.load()
        if rule in self._rules:
            self._rules.remove(rule)
            self._save()
            return True
        return False

    def _save(self) -> None:
        """Save rules to file."""
        rules_file = self.project_root / ".cursorrules"
        content = "\n".join(self._rules)
        rules_file.write_text(content)

    def has_rules(self) -> bool:
        """Check if rules exist."""
        self.load()
        return len(self._rules) > 0
