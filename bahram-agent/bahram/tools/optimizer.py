from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class OptimizationSuggestion:

    file: str
    line: int
    type: str
    severity: str
    description: str
    before: str
    after: str
    impact: str

class PerformanceOptimizer:

    def __init__(self) -> None:
        self._rules: list[tuple[str, str, str, str, str]] = [

            (r"for .+ in range\(len\((.+)\)\)", r"for i, item in enumerate(\1)", "Use enumerate instead of range(len())", "performance", "medium"),
            (r"\.append\((.+)\)\s*\n", r".append(\1)  # Consider list comprehension\n", "Consider list comprehension for multiple appends", "performance", "medium"),
            (r"if (.+) in \[(.+)\]", r"if \1 in {\2}", "Use set for membership testing", "performance", "high"),
            (r"string\s*\+\s*string", r"f\"string\"", "Consider f-strings for string concatenation", "readability", "low"),
            (r"dict\.keys\(\)", r"dict", "Don't call .keys() unnecessarily", "performance", "low"),
            (r"list\((.+)\)", r"\1[:]", "Use slicing instead of list() for copying", "performance", "medium"),
            (r"while True:", r"while True:  # Consider loop limit", "Add loop limit for safety", "performance", "medium"),
            (r"except Exception:", r"except Exception as e:", "Catch specific exception with 'as'", "readability", "low"),
        ]

    async def analyze(self, file_path: str) -> list[OptimizationSuggestion]:
        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                content = f.read()
                lines = content.split("\n")

            suggestions = []
            for i, line in enumerate(lines, 1):
                for pattern, replacement, description, opt_type, impact in self._rules:
                    if re.search(pattern, line):
                        new_line = re.sub(pattern, replacement, line)
                        suggestions.append(OptimizationSuggestion(
                            file=file_path,
                            line=i,
                            type=opt_type,
                            severity=impact,
                            description=description,
                            before=line.strip(),
                            after=new_line.strip(),
                            impact=impact,
                        ))

            return suggestions

        except Exception as e:
            logger.warning(f"Failed to analyze {file_path}: {e}")
            return []

    def format_suggestions(self, suggestions: list[OptimizationSuggestion]) -> str:
        if not suggestions:
            return "No optimization suggestions!"

        lines = ["## Performance Optimization Report", ""]

        by_impact = {}
        for s in suggestions:
            if s.impact not in by_impact:
                by_impact[s.impact] = []
            by_impact[s.impact].append(s)

        impact_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}

        for impact in ["high", "medium", "low"]:
            if impact in by_impact:
                lines.append(f"### {impact_emoji.get(impact, '⚪')} {impact.upper()} Impact")
                for s in by_impact[impact]:
                    lines.append(f"- **{s.file}:{s.line}** - {s.description}")
                    lines.append(f"  Before: `{s.before}`")
                    lines.append(f"  After: `{s.after}`")
                lines.append("")

        return "\n".join(lines)

    def get_summary(self, suggestions: list[OptimizationSuggestion]) -> dict[str, int]:
        summary = {"high": 0, "medium": 0, "low": 0}
        for s in suggestions:
            summary[s.impact] = summary.get(s.impact, 0) + 1
        return summary
