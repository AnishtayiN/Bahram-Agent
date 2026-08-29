from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class DocSection:
    ""

    name: str
    content: str
    level: int = 1

class SmartDocGenerator:
    ""

    def __init__(self) -> None:
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
        ""
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
        ""
        sections = []

        docstring = self._extract_module_docstring(content)
        sections.append(DocSection(
            name="Overview",
            content=docstring or f"Documentation for {filename}",
        ))

        classes = self._extract_classes(content)
        if classes:
            class_content = []
            for cls in classes:
                class_doc = self._document_class(cls)
                class_content.append(class_doc)
            sections.append(DocSection(
                name="Classes",
                content="\n\n".join(class_content),
            ))

        functions = self._extract_functions(content)
        if functions:
            func_content = []
            for func in functions:
                func_doc = self._document_function(func)
                func_content.append(func_doc)
            sections.append(DocSection(
                name="Functions",
                content="\n\n".join(func_content),
            ))

        if include_examples:
            examples = self._generate_examples(classes, functions)
            if examples:
                sections.append(DocSection(
                    name="Examples",
                    content=examples,
                ))

        return sections

    def _extract_module_docstring(self, content: str) -> str:
        ""
        match = re.search(r'""', content, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r"''", content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_classes(self, content: str) -> list[dict]:
        ""
        classes = []
        pattern = r'class\s+(\w+)\s*(?:\(([^)]*)\))?:\s*\n(?:\s+"")?'
        for match in re.finditer(pattern, content, re.DOTALL):
            classes.append({
                "name": match.group(1),
                "parent": match.group(2),
                "docstring": match.group(3) or "",
            })
        return classes

    def _extract_functions(self, content: str) -> list[dict]:
        ""
        functions = []
        pattern = r'def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*(\w+))?:\s*\n(?:\s+"")?'
        for match in re.finditer(pattern, content, re.DOTALL):
            if not match.group(1).startswith("_"):
                functions.append({
                    "name": match.group(1),
                    "args": match.group(2),
                    "return_type": match.group(3),
                    "docstring": match.group(4) or "",
                })
        return functions

    def _document_class(self, cls: dict) -> str:
        ""
        lines = [f"### {cls['name']}"]
        if cls["parent"]:
            lines.append(f" Inherits from: `{cls['parent']}`")
        if cls["docstring"]:
            lines.append(f"\n{cls['docstring']}")
        return "\n".join(lines)

    def _document_function(self, func: dict) -> str:
        ""
        lines = [f"#### `{func['name']}({func['args']})`"]
        if func["return_type"]:
            lines.append(f" Returns: `{func['return_type']}`")
        if func["docstring"]:
            lines.append(f"\n{func['docstring']}")
        return "\n".join(lines)

    def _generate_examples(self, classes: list, functions: list) -> str:
        ""
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
        ""
        lines = []
        for section in sections:
            lines.append(f"{'#' * section.level} {section.name}")
            lines.append("")
            lines.append(section.content)
            lines.append("")
        return "\n".join(lines)
