from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class SupplyChainIssue:

    package: str
    severity: str
    description: str
    recommendation: str

class SupplyChainChecker:

    def __init__(self, data_dir: str = "data/security") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._issues: list[SupplyChainIssue] = []

    def check_python_packages(self) -> list[SupplyChainIssue]:
        issues = []

        try:

            result = subprocess.run(
                ["pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                packages = json.loads(result.stdout)

                vulnerable = self._get_vulnerable_packages()
                for pkg in packages:
                    name = pkg.get("name", "").lower()
                    version = pkg.get("version", "")
                    if name in vulnerable:
                        issues.append(SupplyChainIssue(
                            package=f"{name}=={version}",
                            severity="high",
                            description=f"Known vulnerability in {name}",
                            recommendation=f"Update {name} to latest version",
                        ))
        except Exception as e:
            logger.warning(f"Failed to check packages: {e}")

        return issues

    def _get_vulnerable_packages(self) -> dict[str, str]:
        return {
            "requests": "CVE-2023-32681",
            "flask": "CVE-2023-30861",
            "django": "CVE-2023-31047",
            "pillow": "CVE-2023-44271",
            "cryptography": "CVE-2023-49083",
        }

    def check_file_permissions(self, path: str) -> list[SupplyChainIssue]:
        issues = []
        file_path = Path(path)

        if file_path.exists():

            import stat
            mode = file_path.stat().st_mode
            if mode & stat.S_IWOTH:
                issues.append(SupplyChainIssue(
                    package=str(path),
                    severity="medium",
                    description="File is world-writable",
                    recommendation="Remove world-write permission",
                ))

        return issues

    def scan_dependencies(self, requirements_file: str = "requirements.txt") -> list[SupplyChainIssue]:
        issues = []
        req_path = Path(requirements_file)

        if req_path.exists():
            try:
                content = req_path.read_text()
                for line in content.split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):

                        if "==" not in line and ">=" not in line and "<=" not in line:
                            issues.append(SupplyChainIssue(
                                package=line,
                                severity="low",
                                description="Unpinned dependency version",
                                recommendation=f"Pin version for {line}",
                            ))
            except Exception as e:
                logger.warning(f"Failed to scan dependencies: {e}")

        return issues

    def get_all_issues(self) -> list[dict]:
        issues = []
        issues.extend(self.check_python_packages())
        issues.extend(self.scan_dependencies())
        return [
            {
                "package": i.package,
                "severity": i.severity,
                "description": i.description,
                "recommendation": i.recommendation,
            }
            for i in issues
        ]
