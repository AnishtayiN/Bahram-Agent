from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class CursorRules:
    def __init__(self, project_root: str = ".") -> None:
        self.project_root = Path(project_root)
        self._rules: list[str] = []
        self._loaded = False

    def load(self) -> None:
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
        self.load()
        return self._rules.copy()

    def get_rules_text(self) -> str:
        rules = self.get_rules()
        if not rules:
            return ""

        lines = ["## Cursor Rules", ""]
        for rule in rules:
            lines.append(f"- {rule}")
        return "\n".join(lines)

    def add_rule(self, rule: str) -> None:
        self.load()
        if rule not in self._rules:
            self._rules.append(rule)
            self._save()

    def remove_rule(self, rule: str) -> bool:
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
        self.load()
        return len(self._rules) > 0
