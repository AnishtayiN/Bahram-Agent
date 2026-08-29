"""Supply-chain advisory checking for Bahram Agent."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Advisory:
    """A supply-chain advisory."""

    id: str
    package: str
    affected_versions: str
    fixed_version: str = ""
    description: str = ""
    severity: str = "high"  # low, medium, high, critical


# Known compromised packages
KNOWN_ADVISORIES = [
    Advisory(
        id="BAHRAM-2024-001",
        package="mistralai",
        affected_versions="==2.4.6",
        description="Compromised version with credential exfiltration",
        severity="critical",
    ),
]


class SupplyChainChecker:
    """Check for known compromised packages."""

    def __init__(self) -> None:
        self._advisories = KNOWN_ADVISORIES
        self._acked: set[str] = set()

    def check_packages(self, installed_packages: dict[str, str]) -> list[Advisory]:
        """Check installed packages against advisories.

        Args:
            installed_packages: Dict of package_name -> version

        Returns:
            List of matching advisories
        """
        findings = []

        for advisory in self._advisories:
            if advisory.id in self._acked:
                continue

            installed_version = installed_packages.get(advisory.package)
            if installed_version:
                # Check if version matches affected range
                if self._version_matches(installed_version, advisory.affected_versions):
                    findings.append(advisory)

        return findings

    def _version_matches(self, installed: str, affected: str) -> bool:
        """Check if installed version matches affected range."""
        # Simple exact match for now
        clean_installed = installed.lstrip("=<>!~")
        clean_affected = affected.lstrip("=<>!~")
        return clean_installed == clean_affected

    def acknowledge(self, advisory_id: str) -> bool:
        """Acknowledge an advisory."""
        for advisory in self._advisories:
            if advisory.id == advisory_id:
                self._acked.add(advisory_id)
                return True
        return False

    def get_findings(self, installed_packages: dict[str, str]) -> list[dict]:
        """Get findings as dicts."""
        advisories = self.check_packages(installed_packages)
        return [
            {
                "id": a.id,
                "package": a.package,
                "severity": a.severity,
                "description": a.description,
            }
            for a in advisories
        ]
