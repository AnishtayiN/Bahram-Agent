"""
Ai generator.

Public objects: ``GeneratedFile``, ``AICodeGenerator``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class GeneratedFile:
    """
    Generated file.

    Attributes:
        path (str): filesystem path to operate on.
        content (str): text content to process.
        language (str): language string.
        description (str): human readable description.
    """

    path: str
    content: str
    language: str
    description: str = ""


class AICodeGenerator:
    """
    Ai code generator.
    """

    def __init__(self) -> None:
        """
        Initialise a AICodeGenerator instance.
        """
        self._templates: dict[str, dict] = {
            "fastapi": {
                "files": [
                    {"path": "main.py", "language": "python"},
                    {"path": "requirements.txt", "language": "text"},
                    {"path": "Dockerfile", "language": "dockerfile"},
                    {"path": "README.md", "language": "markdown"},
                ],
            },
            "react": {
                "files": [
                    {"path": "src/App.tsx", "language": "typescript"},
                    {"path": "src/index.tsx", "language": "typescript"},
                    {"path": "package.json", "language": "json"},
                    {"path": "README.md", "language": "markdown"},
                ],
            },
            "cli": {
                "files": [
                    {"path": "main.py", "language": "python"},
                    {"path": "requirements.txt", "language": "text"},
                    {"path": "README.md", "language": "markdown"},
                ],
            },
        }

    async def generate(
        self,
        description: str,
        framework: str = "fastapi",
        output_dir: str = "generated",
    ) -> list[GeneratedFile]:
        """
        Generate.

        Args:
            description (str): human readable description.
            framework (str): framework string. Defaults to ``'fastapi'``.
            output_dir (str): output dir string. Defaults to ``'generated'``.

        Returns:
            list[GeneratedFile]: a sequence of GeneratedFile entries (empty when there is nothing to
                report).

        Note:
            Coroutine - must be awaited.
        """
        template = self._templates.get(framework, {})
        if not template:
            return []

        files = []
        for file_spec in template["files"]:
            content = await self._generate_file(
                description=description,
                file_path=file_spec["path"],
                language=file_spec["language"],
                framework=framework,
            )
            files.append(
                GeneratedFile(
                    path=file_spec["path"],
                    content=content,
                    language=file_spec["language"],
                )
            )

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        for file in files:
            file_path = output_path / file.path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(file.content)

        return files

    async def _generate_file(
        self,
        description: str,
        file_path: str,
        language: str,
        framework: str,
    ) -> str:
        if language == "python" and framework == "fastapi":
            return self._generate_fastapi_main(description)
        elif language == "python" and framework == "cli":
            return self._generate_cli_main(description)
        elif language == "typescript" and framework == "react":
            return self._generate_react_app(description)
        elif file_path == "requirements.txt":
            return self._generate_requirements(framework)
        elif file_path == "package.json":
            return self._generate_package_json(description)
        elif file_path == "Dockerfile":
            return self._generate_dockerfile(framework)
        elif file_path == "README.md":
            return self._generate_readme(description, framework)
        return ""

    def _generate_fastapi_main(self, description: str) -> str:
        return ""

    def _generate_cli_main(self, description: str) -> str:
        return ""

    def _generate_react_app(self, description: str) -> str:
        return ""

    def _generate_requirements(self, framework: str) -> str:
        requirements = {
            "fastapi": "fastapi>=0.104.0\\nuvicorn>=0.24.0\\npydantic>=2.5.0",
            "cli": "click>=8.1.0\\nrich>=13.0.0",
        }
        return requirements.get(framework, "")

    def _generate_package_json(self, description: str) -> str:
        return ""

    def _generate_dockerfile(self, framework: str) -> str:
        if framework == "fastapi":
            return ""
        return ""

    def _generate_readme(self, description: str, framework: str) -> str:
        return ""
