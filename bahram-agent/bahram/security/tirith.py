"""Tirith-style pre-execution content scanner for Bahram Agent."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Result of a content scan."""

    safe: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocked: list[str] = field(default_factory=list)


class TirithScanner:
    """Pre-execution content scanner."""

    def __init__(self) -> None:
        self._dangerous_patterns: list[tuple[str, str, str]] = [
            # (pattern, severity, description)
            (r"rm\s+-rf\s+/", "critical", "Recursive delete from root"),
            (r"mkfs\.", "critical", "Format filesystem"),
            (r"dd\s+if=.*of=/dev/", "critical", "Direct disk write"),
            (r"chmod\s+777", "high", "World-writable permissions"),
            (r"curl.*\|\s*(ba)?sh", "high", "Pipe to shell"),
            (r"wget.*\|\s*(ba)?sh", "high", "Pipe to shell"),
            (r"eval\s*\(", "medium", "Dynamic code evaluation"),
            (r"exec\s*\(", "medium", "Dynamic code execution"),
            (r"__import__", "medium", "Dynamic import"),
            (r"subprocess\.call.*shell=True", "medium", "Shell injection risk"),
            (r"os\.system", "medium", "Shell injection risk"),
        ]
        self._blocked_patterns: list[str] = [
            r"password\s*=\s*['\"]",
            r"secret\s*=\s*['\"]",
            r"api_key\s*=\s*['\"]",
            r"token\s*=\s*['\"]",
        ]

    def scan(self, content: str) -> ScanResult:
        """Scan content for security issues."""
        issues = []
        warnings = []
        blocked = []

        # Check dangerous patterns
        for pattern, severity, description in self._dangerous_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                if severity == "critical":
                    blocked.append(description)
                elif severity == "high":
                    issues.append(description)
                else:
                    warnings.append(description)

        # Check blocked patterns
        for pattern in self._blocked_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                blocked.append(f"Potential secret exposure: {pattern}")

        safe = len(blocked) == 0 and len(issues) == 0
        return ScanResult(
            safe=safe,
            issues=issues,
            warnings=warnings,
            blocked=blocked,
        )

    def scan_command(self, command: str) -> ScanResult:
        """Scan a command before execution."""
        return self.scan(command)

    def scan_code(self, code: str) -> ScanResult:
        """Scan code before execution."""
        return self.scan(code)

    def add_dangerous_pattern(self, pattern: str, severity: str, description: str) -> None:
        """Add a dangerous pattern."""
        self._dangerous_patterns.append((pattern, severity, description))

    def add_blocked_pattern(self, pattern: str) -> None:
        """Add a blocked pattern."""
        self._blocked_patterns.append(pattern)

    def get_scan_report(self, content: str) -> str:
        """Get a formatted scan report."""
        result = self.scan(content)

        lines = ["=== Security Scan Report ===", ""]

        if result.safe:
            lines.append("Status: SAFE")
        else:
            lines.append("Status: UNSAFE")

        if result.blocked:
            lines.append("\nBLOCKED:")
            for item in result.blocked:
                lines.append(f"  - {item}")

        if result.issues:
            lines.append("\nISSUES:")
            for item in result.issues:
                lines.append(f"  - {item}")

        if result.warnings:
            lines.append("\nWARNINGS:")
            for item in result.warnings:
                lines.append(f"  - {item}")

        return "\n".join(lines)
