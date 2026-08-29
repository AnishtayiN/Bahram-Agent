"""Dependency analysis tool for Bahram Agent."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Dependency:
    """A dependency."""

    name: str
    version: str = ""
    source: str = ""  # pip, npm, requirements.txt, package.json
    is_direct: bool = True


class DependencyAnalyzer:
    """Analyze project dependencies."""

    def __init__(self, project_root: str = ".") -> None:
        self.project_root = Path(project_root)

    async def analyze(self) -> dict[str, Any]:
        """Analyze project dependencies."""
        deps = {
            "python": await self._analyze_python(),
            "javascript": await self._analyze_javascript(),
            "total": 0,
        }
        deps["total"] = len(deps["python"]) + len(deps["javascript"])
        return deps

    async def _analyze_python(self) -> list[Dependency]:
        """Analyze Python dependencies."""
        deps = []

        # Check requirements.txt
        req_file = self.project_root / "requirements.txt"
        if req_file.exists():
            content = req_file.read_text()
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = re.split(r"[>=<~!]", line)
                    name = parts[0].strip()
                    version = parts[1] if len(parts) > 1 else ""
                    deps.append(Dependency(name=name, version=version, source="requirements.txt"))

        # Check pyproject.toml
        pyproject = self.project_root / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()
            # Simple regex extraction
            matches = re.findall(r'"([a-zA-Z0-9_-]+)(?:[>=<~!].*?)?"', content)
            for match in matches:
                if match not in [d.name for d in deps]:
                    deps.append(Dependency(name=match, source="pyproject.toml"))

        return deps

    async def _analyze_javascript(self) -> list[Dependency]:
        """Analyze JavaScript dependencies."""
        deps = []

        # Check package.json
        pkg_file = self.project_root / "package.json"
        if pkg_file.exists():
            import json
            content = json.loads(pkg_file.read_text())
            for name, version in content.get("dependencies", {}).items():
                deps.append(Dependency(name=name, version=version, source="package.json"))
            for name, version in content.get("devDependencies", {}).items():
                deps.append(Dependency(name=name, version=version, source="package.json (dev)"))

        return deps

    def get_report(self, deps: dict[str, Any]) -> str:
        """Get dependency report."""
        lines = ["## Dependency Report", ""]

        if deps["python"]:
            lines.append("### Python Dependencies")
            for dep in deps["python"]:
                lines.append(f"- {dep.name} {dep.version} ({dep.source})")
            lines.append("")

        if deps["javascript"]:
            lines.append("### JavaScript Dependencies")
            for dep in deps["javascript"]:
                lines.append(f"- {dep.name} {dep.version} ({dep.source})")
            lines.append("")

        lines.append(f"**Total: {deps['total']} dependencies**")
        return "\n".join(lines)

    def check_outdated(self, deps: dict[str, Any]) -> list[dict]:
        """Check for outdated dependencies."""
        outdated = []
        # This would need network access to check PyPI/npm
        # Simplified version
        return outdated
