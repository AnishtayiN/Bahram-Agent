from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DocumentationGenerator:
    def __init__(self) -> None:
        self._templates: dict[str, str] = {
            "readme": self._get_readme_template(),
            "api": self._get_api_template(),
            "changelog": self._get_changelog_template(),
        }

    async def generate(self, source_path: str, output_path: str, doc_type: str = "readme") -> bool:
        try:
            source = Path(source_path)
            if not source.exists():
                return False

            if doc_type == "readme":
                content = await self._generate_readme(source)
            elif doc_type == "api":
                content = await self._generate_api_docs(source)
            elif doc_type == "changelog":
                content = await self._generate_changelog(source)
            else:
                return False

            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(content)
            return True

        except Exception as e:
            logger.error(f"Documentation generation failed: {e}")
            return False

    async def _generate_readme(self, source: Path) -> str:
        lines = [f"# {source.name}", ""]

        for py_file in sorted(source.glob("**/*.py")):
            rel_path = py_file.relative_to(source)
            docstring = self._extract_docstring(py_file)
            if docstring:
                lines.append(f"## {rel_path.stem}")
                lines.append(docstring)
                lines.append("")

        return "\n".join(lines)

    async def _generate_api_docs(self, source: Path) -> str:
        lines = ["# API Documentation", ""]

        for py_file in sorted(source.glob("**/*.py")):
            rel_path = py_file.relative_to(source)
            content = py_file.read_text(errors="replace")

            import re

            classes = re.findall(r"class (\w+).*:", content)
            functions = re.findall(r"def (\w+)\(.*\):", content)

            if classes or functions:
                lines.append(f"## {rel_path.stem}")
                for cls in classes:
                    lines.append(f"- class `{cls}`")
                for func in functions:
                    if not func.startswith("_"):
                        lines.append(f"- `{func}()`")
                lines.append("")

        return "\n".join(lines)

    async def _generate_changelog(self, source: Path) -> str:
        return ""

    def _extract_docstring(self, file_path: Path) -> str:
        try:
            content = file_path.read_text(errors="replace")
            import re

            match = re.search(r'"""(.*?)"""', content, re.DOTALL)
            if match:
                return match.group(1).strip()
            match = re.search(r"'''(.*?)'''", content, re.DOTALL)
            if match:
                return match.group(1).strip()
        except Exception:
            pass
        return ""

    def _get_readme_template(self) -> str:
        return "# {name}\n\n{description}\n"

    def _get_api_template(self) -> str:
        return "# API Documentation\n\n{endpoints}\n"

    def _get_changelog_template(self) -> str:
        return "# Changelog\n\n{entries}\n"
