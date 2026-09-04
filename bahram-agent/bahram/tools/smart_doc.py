"""
Smart doc.

Public objects: ``DocSection``, ``SmartDocGenerator``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from re import error

logger = logging.getLogger(__name__)


@dataclass
class DocSection:
    """
    Doc section.

    Attributes:
        name (str): name of the object.
        content (str): text content to process.
        level (int): numeric value for level.
    """

    name: str
    content: str
    level: int = 1


class SmartDocGenerator:
    """
    Smart doc generator.
    """

    def __init__(self) -> None:
        """
        Initialise a SmartDocGenerator instance.
        """
        self._templates: dict[str, str] = {
            "markdown": "# {title}\n\n{content}\n",
            "rst": "{title}\n{underline}\n\n{content}\n",
            "html": "<html><body><h1>{title}</h1>{content}</body></html>",
        }

    async def generate(
        self,
        source_path: str,
        output_path: str,
        format: str = "markdown",
        include_examples: bool = True,
    ) -> bool:
        """
        Generate.

        Args:
            source_path (str): source path string.
            output_path (str): output path string.
            format (str): format string. Defaults to ``'markdown'``.
            include_examples (bool): when ``True``, enable include examples. Defaults to ``True``.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        try:
            source = Path(source_path)
            if not source.exists():
                return False

            content = source.read_text(errors="replace")
            sections = await self._analyze_code(content, source.name, include_examples)

            doc_content = self._render_sections(sections, format)

            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(doc_content)
            return True

        except Exception as e:
            logger.error(f"Documentation generation failed: {e}")
            return False

    async def _analyze_code(
        self,
        content: str,
        filename: str,
        include_examples: bool,
    ) -> list[DocSection]:
        sections = []

        docstring = self._extract_module_docstring(content)
        sections.append(
            DocSection(
                name="Overview",
                content=docstring or f"Documentation for {filename}",
            )
        )

        classes = self._extract_classes(content)
        if classes:
            class_content = []
            for cls in classes:
                class_doc = self._document_class(cls)
                class_content.append(class_doc)
            sections.append(
                DocSection(
                    name="Classes",
                    content="\n\n".join(class_content),
                )
            )

        functions = self._extract_functions(content)
        if functions:
            func_content = []
            for func in functions:
                func_doc = self._document_function(func)
                func_content.append(func_doc)
            sections.append(
                DocSection(
                    name="Functions",
                    content="\n\n".join(func_content),
                )
            )

        if include_examples:
            examples = self._generate_examples(classes, functions)
            if examples:
                sections.append(
                    DocSection(
                        name="Examples",
                        content=examples,
                    )
                )

        return sections

    #: Captures a triple-quoted string, accepting either quote style.  The
    #: earlier patterns were bare ``""`` / ``''`` literals with no capture
    #: group, so every ``match.group(1)`` raised ``IndexError``.
    _DOCSTRING = r'(?:"{3}(.*?)"{3}|\'{3}(.*?)\'{3})'

    @classmethod
    def _group(cls, match: re.Match, *indexes: int) -> str:
        """Return the first non-empty capture group among ``indexes``."""
        for index in indexes:
            try:
                value = match.group(index)
            except (IndexError, error):
                value = None
            if value:
                return value.strip()
        return ""

    def _extract_module_docstring(self, content: str) -> str:
        match = re.search(self._DOCSTRING, content, re.DOTALL)
        if match:
            return self._group(match, 1, 2)
        return ""

    def _extract_classes(self, content: str) -> list[dict]:
        classes = []
        # The docstring is optional - a symbol without one is still listed,
        # it just gets an empty ``docstring`` value.
        pattern = (
            r"class\s+(\w+)\s*(?:\(([^)]*)\))?:[ \t]*\n(?:[ \t]*" + self._DOCSTRING + r")?"
        )
        for match in re.finditer(pattern, content, re.DOTALL):
            classes.append(
                {
                    "name": match.group(1),
                    "parent": match.group(2),
                    "docstring": self._group(match, 3, 4),
                }
            )
        return classes

    def _extract_functions(self, content: str) -> list[dict]:
        functions = []
        pattern = (
            r"def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*([\w\[\], |]+?))?:[ \t]*\n"
            r"(?:[ \t]*" + self._DOCSTRING + r")?"
        )
        for match in re.finditer(pattern, content, re.DOTALL):
            if not match.group(1).startswith("_"):
                functions.append(
                    {
                        "name": match.group(1),
                        "args": match.group(2),
                        "return_type": match.group(3),
                        "docstring": self._group(match, 4, 5),
                    }
                )
        return functions

    def _document_class(self, cls: dict) -> str:
        lines = [f"### {cls['name']}"]
        if cls["parent"]:
            lines.append(f" Inherits from: `{cls['parent']}`")
        if cls["docstring"]:
            lines.append(f"\n{cls['docstring']}")
        return "\n".join(lines)

    def _document_function(self, func: dict) -> str:
        lines = [f"#### `{func['name']}({func['args']})`"]
        if func["return_type"]:
            lines.append(f" Returns: `{func['return_type']}`")
        if func["docstring"]:
            lines.append(f"\n{func['docstring']}")
        return "\n".join(lines)

    def _generate_examples(self, classes: list, functions: list) -> str:
        examples = ["```python", "# Usage Examples", ""]

        for cls in classes[:3]:
            examples.append(f"# Create {cls['name']} instance")
            examples.append(f"instance = {cls['name']}()")
            examples.append("")

        for func in functions[:3]:
            examples.append(f"# Call {func['name']}")
            examples.append(f"result = {func['name']}()")
            examples.append("")

        examples.append("```")
        return "\n".join(examples)

    def _render_sections(self, sections: list[DocSection], format: str) -> str:
        lines = []
        for section in sections:
            lines.append(f"{'#' * section.level} {section.name}")
            lines.append("")
            lines.append(section.content)
            lines.append("")
        return "\n".join(lines)
