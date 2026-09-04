"""
Security scan.

Public objects: ``SecurityIssue``, ``SecurityScanner``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SecurityIssue:
    """
    Security issue.

    Attributes:
        file (str): file string.
        line (int): numeric value for line.
        severity (str): severity string.
        category (str): category string.
        description (str): human readable description.
        recommendation (str): recommendation string.
    """

    file: str
    line: int
    severity: str
    category: str
    description: str
    recommendation: str


class SecurityScanner:
    """
    Security scanner.
    """

    def __init__(self) -> None:
        """
        Initialise a SecurityScanner instance.
        """
        self._patterns: list[tuple[str, str, str, str, str]] = [
            (
                r"eval\(",
                "critical",
                "code_injection",
                "eval() usage",
                "Avoid eval(), use ast.literal_eval()",
            ),
            (r"exec\(", "critical", "code_injection", "exec() usage", "Avoid exec()"),
            (
                r"os\.system\(",
                "high",
                "command_injection",
                "os.system() usage",
                "Use subprocess with shell=False",
            ),
            (
                r"subprocess\.call.*shell=True",
                "high",
                "command_injection",
                "Shell=True subprocess",
                "Use shell=False",
            ),
            (
                r"pickle\.loads?\(",
                "high",
                "deserialization",
                "Pickle deserialization",
                "Use JSON or safer format",
            ),
            (
                r"yaml\.load\(",
                "medium",
                "deserialization",
                "Unsafe YAML load",
                "Use yaml.safe_load()",
            ),
            (
                r"password\s*=\s*['\"]",
                "high",
                "hardcoded_secret",
                "Hardcoded password",
                "Use environment variables",
            ),
            (
                r"secret\s*=\s*['\"]",
                "high",
                "hardcoded_secret",
                "Hardcoded secret",
                "Use environment variables",
            ),
            (
                r"api_key\s*=\s*['\"]",
                "high",
                "hardcoded_secret",
                "Hardcoded API key",
                "Use environment variables",
            ),
            (r"SELECT.*FROM", "medium", "sql", "Raw SQL query", "Use parameterized queries"),
            (r"INSERT.*INTO", "medium", "sql", "Raw SQL query", "Use parameterized queries"),
            (r"UPDATE.*SET", "medium", "sql", "Raw SQL query", "Use parameterized queries"),
            (r"DELETE.*FROM", "medium", "sql", "Raw SQL query", "Use parameterized queries"),
        ]

    async def scan_file(self, file_path: str) -> list[SecurityIssue]:
        """
        Scan file.

        Args:
            file_path (str): path of the file to operate on.

        Returns:
            list[SecurityIssue]: a sequence of SecurityIssue entries (empty when there is nothing to
                report).

        Note:
            Coroutine - must be awaited.
        """
        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                content = f.read()
                lines = content.split("\n")

            issues = []
            for i, line in enumerate(lines, 1):
                for pattern, severity, category, description, recommendation in self._patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        issues.append(
                            SecurityIssue(
                                file=file_path,
                                line=i,
                                severity=severity,
                                category=category,
                                description=description,
                                recommendation=recommendation,
                            )
                        )

            return issues

        except Exception as e:
            logger.warning(f"Failed to scan {file_path}: {e}")
            return []

    async def scan_directory(self, dir_path: str) -> list[SecurityIssue]:
        """
        Scan directory.

        Args:
            dir_path (str): dir path string.

        Returns:
            list[SecurityIssue]: a sequence of SecurityIssue entries (empty when there is nothing to
                report).

        Note:
            Coroutine - must be awaited.
        """
        issues = []
        path = Path(dir_path)

        for file_path in path.rglob("*.py"):
            file_issues = await self.scan_file(str(file_path))
            issues.extend(file_issues)

        return issues

    def get_report(self, issues: list[SecurityIssue]) -> str:
        """
        Return the report.

        Args:
            issues (list[SecurityIssue]): collection of issues.

        Returns:
            str: the rendered string.
        """
        if not issues:
            return "No security issues found!"

        lines = ["## Security Report", ""]

        by_severity = {}
        for issue in issues:
            if issue.severity not in by_severity:
                by_severity[issue.severity] = []
            by_severity[issue.severity].append(issue)

        severity_emoji = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
        }

        for severity in ["critical", "high", "medium", "low"]:
            if severity in by_severity:
                lines.append(f"### {severity_emoji.get(severity, '⚪')} {severity.upper()}")
                for issue in by_severity[severity]:
                    lines.append(f"- {issue.file}:{issue.line} - {issue.description}")
                    lines.append(f"  Recommendation: {issue.recommendation}")
                lines.append("")

        return "\n".join(lines)

    def get_summary(self, issues: list[SecurityIssue]) -> dict[str, int]:
        """
        Return the summary.

        Args:
            issues (list[SecurityIssue]): collection of issues.

        Returns:
            dict[str, int]: a mapping of str, int.
        """
        summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for issue in issues:
            summary[issue.severity] = summary.get(issue.severity, 0) + 1
        return summary
