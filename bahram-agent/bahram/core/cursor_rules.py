"""
Cursor rules.

Public objects: ``CursorRules``.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class CursorRules:
    """
    Cursor rules.
    """

    def __init__(self, project_root: str = ".") -> None:
        """
        Initialise a CursorRules instance.

        Args:
            project_root (str): project root string. Defaults to ``'.'``.
        """
        self.project_root = Path(project_root)
        self._rules: list[str] = []
        self._loaded = False

    def load(self) -> None:
        """
        Load.
        """
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
        """
        Return the rules.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        self.load()
        return self._rules.copy()

    def get_rules_text(self) -> str:
        """
        Return the rules text.

        Returns:
            str: the rendered string.
        """
        rules = self.get_rules()
        if not rules:
            return ""

        lines = ["## Cursor Rules", ""]
        for rule in rules:
            lines.append(f"- {rule}")
        return "\n".join(lines)

    def add_rule(self, rule: str) -> None:
        """
        Add rule.

        Args:
            rule (str): rule string.
        """
        self.load()
        if rule not in self._rules:
            self._rules.append(rule)
            self._save()

    def remove_rule(self, rule: str) -> bool:
        """
        Remove rule.

        Args:
            rule (str): rule string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        self.load()
        if rule in self._rules:
            self._rules.remove(rule)
            self._save()
            return True
        return False

    def _save(self) -> None:
        rules_file = self.project_root / ".cursorrules"
        content = "\n".join(self._rules)
        rules_file.write_text(content)

    def has_rules(self) -> bool:
        """
        Return ``True`` when the object has rules.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        self.load()
        return len(self._rules) > 0
