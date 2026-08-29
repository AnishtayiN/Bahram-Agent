"""Cursor rules and context file system for Bahram Agent."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# Standard context file names (priority order)
CONTEXT_FILE_NAMES = [
    ".bahram.md",
    "AGENTS.md",
    "CLAUDE.md",
    "SOUL.md",
    ".cursorrules",
    "CONTEXT.md",
    "INSTRUCTIONS.md",
    ".opencode",
    "RULES.md",
    "PROMPT.md",
    "SYSTEM.md",
]


class CursorRules:
    """Manage .cursorrules and similar context files."""

    def __init__(self, project_dir: str = ".") -> None:
        self.project_dir = Path(project_dir)
        self._rules_content: Optional[str] = None

    def discover_rules_files(self) -> list[Path]:
        """Discover all rules/context files."""
        found = []

        for filename in CONTEXT_FILE_NAMES:
            filepath = self.project_dir / filename
            if filepath.exists():
                found.append(filepath)
                logger.debug(f"Found rules file: {filepath}")

        # Check .bahram/ directory
        bahram_dir = self.project_dir / ".bahram"
        if bahram_dir.exists():
            for md_file in bahram_dir.glob("*.md"):
                found.append(md_file)

        # Check .cursor/ directory
        cursor_dir = self.project_dir / ".cursor"
        if cursor_dir.exists():
            for md_file in cursor_dir.glob("*.md"):
                found.append(md_file)

        # Check .claude/ directory
        claude_dir = self.project_dir / ".claude"
        if claude_dir.exists():
            for md_file in claude_dir.glob("*.md"):
                found.append(md_file)

        return found

    def load_rules(self) -> str:
        """Load and combine all rules files."""
        if self._rules_content is not None:
            return self._rules_content

        rules_files = self.discover_rules_files()

        if not rules_files:
            return ""

        parts = []
        for filepath in rules_files:
            try:
                content = filepath.read_text(encoding="utf-8")
                parts.append(f"## From {filepath.name}\n\n{content}")
            except Exception as e:
                logger.warning(f"Failed to read {filepath}: {e}")

        self._rules_content = "\n\n---\n\n".join(parts)
        return self._rules_content

    def get_system_prompt_addition(self) -> str:
        """Get rules to add to system prompt."""
        rules = self.load_rules()
        if not rules:
            return ""
        return f"\n\n## Project Rules\n\n{rules}"

    def clear_cache(self) -> None:
        """Clear cached rules."""
        self._rules_content = None
