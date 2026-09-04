from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class GeneratedTest:

    name: str
    code: str
    file_path: str
    test_type: str

class TestGenerator:

    def __init__(self) -> None:
        self._test_templates: dict[str, str] = {
            "unit": '',
            "integration": '',
        }

    async def generate_tests(
        self,
        source_path: str,
        output_dir: str,
        test_type: str = "unit",
    ) -> list[GeneratedTest]:
        try:
            source = Path(source_path)
            if not source.exists():
                return []

            content = source.read_text(errors="replace")
            classes = self._extract_classes(content)
            functions = self._extract_functions(content)

            tests = []

            for cls in classes:
                test_code = await self._generate_class_tests(cls, test_type)
                test_file = Path(output_dir) / f"test_{source.stem}.py"
                tests.append(GeneratedTest(
                    name=f"test_{cls['name'].lower()}",
                    code=test_code,
                    file_path=str(test_file),
                    test_type=test_type,
                ))

            for func in functions:
                test_code = await self._generate_function_tests(func, test_type)
                test_file = Path(output_dir) / f"test_{source.stem}.py"
                tests.append(GeneratedTest(
                    name=f"test_{func['name'].lower()}",
                    code=test_code,
                    file_path=str(test_file),
                    test_type=test_type,
                ))

            if tests:
                output = Path(output_dir)
                output.mkdir(parents=True, exist_ok=True)
                combined_code = self._combine_tests(tests)
                (output / f"test_{source.stem}.py").write_text(combined_code)

            return tests

        except Exception as e:
            logger.warning(f"Failed to generate tests: {e}")
            return []

    def _extract_classes(self, content: str) -> list[dict]:
        classes = []
        pattern = r"class\s+(\w+)\s*(?:\(([^)]*)\))?:"
        for match in re.finditer(pattern, content):
            classes.append({
                "name": match.group(1),
                "parent": match.group(2),
            })
        return classes

    def _extract_functions(self, content: str) -> list[dict]:
        functions = []
        pattern = r"def\s+(\w+)\s*\(([^)]*)\)"
        for match in re.finditer(pattern, content):
            if not match.group(1).startswith("_"):
                functions.append({
                    "name": match.group(1),
                    "args": match.group(2),
                })
        return functions

    async def _generate_class_tests(self, cls: dict, test_type: str) -> str:
        test_methods = ""
        return self._test_templates.get(test_type, "").format(
            module="module",
            class_name=cls["name"],
            init_args="",
            test_methods=test_methods,
        )

    async def _generate_function_tests(self, func: dict, test_type: str) -> str:
        return ''

    def _combine_tests(self, tests: list[GeneratedTest]) -> str:
        lines = ['""', "", "import pytest", ""]
        for test in tests:

            for line in test.code.split("\n"):
                if line.strip() and not line.startswith('"""') and not line.startswith("from "):
                    lines.append(line)
        return "\n".join(lines)
