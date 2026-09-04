from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CodeIssue:
    file: str
    line: int
    severity: str
    category: str
    message: str
    suggestion: str = ""


class CodeReviewTool:
    def __init__(self) -> None:
        self._rules: list[tuple[str, str, str, str]] = [
            (r"print\(", "info", "style", "Consider using logging instead of print"),
            (r"except:", "warning", "error", "Bare except clause - specify exception type"),
            (r"TODO", "info", "todo", "TODO comment found"),
            (r"FIXME", "warning", "todo", "FIXME comment found"),
            (r"HACK", "warning", "style", "HACK comment found - consider refactoring"),
            (r"import \*", "warning", "style", "Wildcard import - prefer explicit imports"),
            (r"eval\(", "error", "security", "eval() usage - potential security risk"),
            (r"exec\(", "error", "security", "exec() usage - potential security risk"),
            (r"__import__", "warning", "security", "Dynamic import - consider static import"),
            (r"len\(.+\) == 0", "info", "style", "Use 'not x' instead of 'len(x) == 0'"),
            (r"is True", "info", "style", "Use 'if x:' instead of 'if x is True:'"),
            (r"is False", "info", "style", "Use 'if not x:' instead of 'if x is False:'"),
            (r"if .+ is not None", "info", "style", "Consider using 'if x:' pattern"),
            (
                r"raise NotImplementedError",
                "info",
                "design",
                "Abstract method - ensure implementation",
            ),
            (r"global ", "warning", "style", "Global variable usage - consider alternatives"),
            (r"lambda .+=", "warning", "style", "Lambda assignment - use def instead"),
        ]

    async def review_file(self, file_path: str) -> list[CodeIssue]:
        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                content = f.read()
                lines = content.split("\n")

            issues = []
            for i, line in enumerate(lines, 1):
                for pattern, severity, category, message in self._rules:
                    if re.search(pattern, line):
                        issues.append(
                            CodeIssue(
                                file=file_path,
                                line=i,
                                severity=severity,
                                category=category,
                                message=message,
                                suggestion=self._get_suggestion(category, line),
                            )
                        )

            return issues

        except Exception as e:
            logger.warning(f"Failed to review {file_path}: {e}")
            return []

    async def review_code(self, code: str, language: str = "python") -> list[CodeIssue]:
        issues = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            for pattern, severity, category, message in self._rules:
                if re.search(pattern, line):
                    issues.append(
                        CodeIssue(
                            file="<code>",
                            line=i,
                            severity=severity,
                            category=category,
                            message=message,
                            suggestion=self._get_suggestion(category, line),
                        )
                    )

        return issues

    def _get_suggestion(self, category: str, line: str) -> str:
        suggestions = {
            "style": "Consider refactoring for better readability",
            "error": "Handle exceptions explicitly",
            "security": "Review for security implications",
            "todo": "Address before merging",
            "design": "Ensure proper implementation",
        }
        return suggestions.get(category, "")

    def get_summary(self, issues: list[CodeIssue]) -> dict[str, int]:
        summary = {"error": 0, "warning": 0, "info": 0}
        for issue in issues:
            summary[issue.severity] = summary.get(issue.severity, 0) + 1
        return summary

    def format_report(self, issues: list[CodeIssue]) -> str:
        if not issues:
            return "No issues found!"

        lines = ["## Code Review Report", ""]
        summary = self.get_summary(issues)
        lines.append(
            f"Errors: {summary['error']} | Warnings: {summary['warning']} | Info: {summary['info']}"
        )
        lines.append("")

        for issue in sorted(issues, key=lambda x: (x.severity, x.file, x.line)):
            severity_emoji = {"error": "🔴", "warning": "🟡", "info": "🔵"}
            lines.append(
                f"{severity_emoji.get(issue.severity, '⚪')} {issue.file}:{issue.line} - "
                f"{issue.message}"
            )
            if issue.suggestion:
                lines.append(f"   💡 {issue.suggestion}")

        return "\n".join(lines)
