"""Context files for Bahram Agent."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ContextFiles:
    """Context files that shape agent behavior in projects."""

    # Standard context file names (in priority order)
    CONTEXT_FILE_NAMES = [
        ".bahram.md",
        "AGENTS.md",
        "CLAUDE.md",
        "SOUL.md",
        ".cursorrules",
        "CONTEXT.md",
        "INSTRUCTIONS.md",
    ]

    def __init__(self, project_dir: str = ".") -> None:
        self.project_dir = Path(project_dir)
        self._context_content: Optional[str] = None

    def discover_context_files(self) -> list[Path]:
        """Discover context files in the project."""
        found = []

        for filename in self.CONTEXT_FILE_NAMES:
            filepath = self.project_dir / filename
            if filepath.exists():
                found.append(filepath)
                logger.debug(f"Found context file: {filepath}")

        # Also check .bahram/ directory
        bahram_dir = self.project_dir / ".bahram"
        if bahram_dir.exists():
            for md_file in bahram_dir.glob("*.md"):
                found.append(md_file)
                logger.debug(f"Found context file: {md_file}")

        return found

    def load_context(self) -> str:
        """Load and combine all context files."""
        if self._context_content is not None:
            return self._context_content

        context_files = self.discover_context_files()

        if not context_files:
            logger.debug("No context files found")
            return ""

        parts = []
        for filepath in context_files:
            try:
                content = filepath.read_text(encoding="utf-8")
                parts.append(f"## From {filepath.name}\n\n{content}")
            except Exception as e:
                logger.warning(f"Failed to read {filepath}: {e}")

        self._context_content = "\n\n---\n\n".join(parts)
        return self._context_content

    def get_system_prompt_addition(self) -> str:
        """Get context to add to system prompt."""
        context = self.load_context()
        if not context:
            return ""

        return f"\n\n## Project Context\n\n{context}"

    def clear_cache(self) -> None:
        """Clear the cached context."""
        self._context_content = None

    def list_found_files(self) -> list[str]:
        """List found context file names."""
        return [str(f.name) for f in self.discover_context_files()]
