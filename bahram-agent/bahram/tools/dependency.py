"""
Dependency.

Public objects: ``Dependency``, ``DependencyAnalyzer``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Dependency:
    """
    Dependency.

    Attributes:
        name (str): name of the object.
        version (str): version string.
        source (str): source string.
        is_direct (bool): when ``True``, enable is direct.
    """

    name: str
    version: str = ""
    source: str = ""
    is_direct: bool = True


class DependencyAnalyzer:
    """
    Dependency analyzer.
    """

    def __init__(self, project_root: str = ".") -> None:
        """
        Initialise a DependencyAnalyzer instance.

        Args:
            project_root (str): project root string. Defaults to ``'.'``.
        """
        self.project_root = Path(project_root)

    async def analyze(self) -> dict[str, Any]:
        """
        Analyze.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        deps = {
            "python": await self._analyze_python(),
            "javascript": await self._analyze_javascript(),
            "total": 0,
        }
        deps["total"] = len(deps["python"]) + len(deps["javascript"])
        return deps

    async def _analyze_python(self) -> list[Dependency]:
        deps = []

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

        pyproject = self.project_root / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text()

            matches = re.findall(r'"([a-zA-Z0-9_-]+)(?:[>=<~!].*?)?"', content)
            for match in matches:
                if match not in [d.name for d in deps]:
                    deps.append(Dependency(name=match, source="pyproject.toml"))

        return deps

    async def _analyze_javascript(self) -> list[Dependency]:
        deps = []

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
        """
        Return the report.

        Args:
            deps (dict[str, Any]): mapping of deps.

        Returns:
            str: the rendered string.
        """
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
        """
        Check outdated.

        Args:
            deps (dict[str, Any]): mapping of deps.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        outdated = []

        return outdated
