"""Tirith pre-execution security scanning for Bahram Agent."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ScanResult:
    """Result of a Tirith scan."""

    safe: bool
    severity: str = "none"  # none, low, medium, high, critical
    title: str = ""
    description: str = ""
    alternatives: list[str] = None

    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []


class TirithScanner:
    """Tirith pre-execution security scanner."""

    def __init__(
        self,
        enabled: bool = True,
        timeout: int = 5,
        fail_open: bool = True,
    ) -> None:
        self.enabled = enabled
        self.timeout = timeout
        self.fail_open = fail_open
        self._binary_path: Optional[str] = None

    def scan_command(self, command: str) -> ScanResult:
        """Scan a command before execution."""
        if not self.enabled:
            return ScanResult(safe=True)

        # Try tirith binary
        if self._binary_path:
            return self._scan_with_tirith(command)

        # Fallback to pattern-based scanning
        return self._scan_patterns(command)

    def _scan_with_tirith(self, command: str) -> ScanResult:
        """Scan using tirith binary."""
        try:
            result = subprocess.run(
                [self._binary_path, "scan", "--command", command],
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode == 0:
                return ScanResult(safe=True)
            else:
                return ScanResult(
                    safe=False,
                    severity="high",
                    title="Tirith blocked command",
                    description=result.stdout[:500],
                )
        except subprocess.TimeoutExpired:
            if self.fail_open:
                return ScanResult(safe=True)
            return ScanResult(safe=False, severity="medium", title="Tirith timeout")
        except Exception as e:
            if self.fail_open:
                return ScanResult(safe=True)
            return ScanResult(safe=False, severity="low", title=f"Tirith error: {e}")

    def _scan_patterns(self, command: str) -> ScanResult:
        """Pattern-based scanning fallback."""
        suspicious = [
            (r"curl\s+.*\|\s*(bash|sh)", "Pipe remote to shell", "high"),
            (r"wget\s+.*\|\s*(bash|sh)", "Pipe remote to shell", "high"),
            (r"bash\s*<\s*\(", "Execute remote script", "high"),
            (r"eval\s*\(", "Dynamic code execution", "medium"),
            (r"exec\s*\(", "Dynamic code execution", "medium"),
            (r"__import__\s*\(", "Dynamic import", "medium"),
            (r"subprocess\.(call|run|Popen)\s*\(", "Subprocess execution", "medium"),
            (r"os\.system\s*\(", "System call", "medium"),
        ]

        import re
        for pattern, title, severity in suspicious:
            if re.search(pattern, command, re.IGNORECASE):
                return ScanResult(
                    safe=False,
                    severity=severity,
                    title=title,
                    description=f"Pattern matched: {pattern}",
                    alternatives=["Use a safer alternative"],
                )

        return ScanResult(safe=True)

    def install_binary(self) -> bool:
        """Try to install tirith binary."""
        try:
            # Download from GitHub releases
            logger.info("Installing tirith...")
            # Placeholder - actual implementation would download binary
            return False
        except Exception as e:
            logger.error(f"Failed to install tirith: {e}")
            return False
