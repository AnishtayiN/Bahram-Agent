"""
Refactor.

Public objects: ``RefactorSuggestion``, ``RefactorTool``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RefactorSuggestion:
    """
    Refactor suggestion.

    Attributes:
        file (str): file string.
        line (int): numeric value for line.
        type (str): type string.
        description (str): human readable description.
        before (str): before string.
        after (str): after string.
    """

    file: str
    line: int
    type: str
    description: str
    before: str
    after: str


class RefactorTool:
    """
    Refactor tool.
    """

    def __init__(self) -> None:
        """
        Initialise a RefactorTool instance.
        """
        self._rules: list[tuple[str, str, str, str]] = [
            (r"if (.+) is True", r"if \1", "Simplify boolean check", "simplify"),
            (r"if (.+) is False", r"if not \1", "Simplify boolean check", "simplify"),
            (r"if (.+) == None", r"if \1 is None", "Use 'is' for None comparison", "pythonic"),
            (
                r"if (.+) != None",
                r"if \1 is not None",
                "Use 'is not' for None comparison",
                "pythonic",
            ),
            (r"len\((.+)\) == 0", r"not \1", "Use 'not' for empty check", "pythonic"),
            (r"len\((.+)\) > 0", r"\1", "Use truthiness for non-empty check", "pythonic"),
            (
                r"\.append\((.+)\)",
                r".append(\1)  # Consider list comprehension",
                "Review append usage",
                "review",
            ),
        ]

    async def analyze(self, file_path: str) -> list[RefactorSuggestion]:
        """
        Analyze.

        Args:
            file_path (str): path of the file to operate on.

        Returns:
            list[RefactorSuggestion]: a sequence of RefactorSuggestion entries (empty when there is
                nothing to report).

        Note:
            Coroutine - must be awaited.
        """
        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                content = f.read()
                lines = content.split("\n")

            suggestions = []
            for i, line in enumerate(lines, 1):
                for pattern, replacement, description, ref_type in self._rules:
                    if re.search(pattern, line):
                        new_line = re.sub(pattern, replacement, line)
                        suggestions.append(
                            RefactorSuggestion(
                                file=file_path,
                                line=i,
                                type=ref_type,
                                description=description,
                                before=line.strip(),
                                after=new_line.strip(),
                            )
                        )

            return suggestions

        except Exception as e:
            logger.warning(f"Failed to analyze {file_path}: {e}")
            return []

    def format_suggestions(self, suggestions: list[RefactorSuggestion]) -> str:
        """
        Format suggestions.

        Args:
            suggestions (list[RefactorSuggestion]): collection of suggestions.

        Returns:
            str: the rendered string.
        """
        if not suggestions:
            return "No refactoring suggestions!"

        lines = ["## Refactoring Suggestions", ""]

        for s in suggestions:
            lines.append(f"### {s.file}:{s.line} ({s.type})")
            lines.append(f"**{s.description}**")
            lines.append(f"Before: `{s.before}`")
            lines.append(f"After: `{s.after}`")
            lines.append("")

        return "\n".join(lines)

    def get_summary(self, suggestions: list[RefactorSuggestion]) -> dict[str, int]:
        """
        Return the summary.

        Args:
            suggestions (list[RefactorSuggestion]): collection of suggestions.

        Returns:
            dict[str, int]: a mapping of str, int.
        """
        summary = {}
        for s in suggestions:
            summary[s.type] = summary.get(s.type, 0) + 1
        return summary
