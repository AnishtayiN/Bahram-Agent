"""
Test generator.

Public objects: ``GeneratedTest``, ``TestGenerator``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class GeneratedTest:
    """
    Generated test.

    Attributes:
        name (str): name of the object.
        code (str): source code to execute.
        file_path (str): path of the file to operate on.
        test_type (str): test type string.
    """

    name: str
    code: str
    file_path: str
    test_type: str


class TestGenerator:
    """
    Test generator.
    """

    def __init__(self) -> None:
        """
        Initialise a TestGenerator instance.
        """
        self._test_templates: dict[str, str] = {
            "unit": "",
            "integration": "",
        }

    async def generate_tests(
        self,
        source_path: str,
        output_dir: str,
        test_type: str = "unit",
    ) -> list[GeneratedTest]:
        """
        Generate tests.

        Args:
            source_path (str): source path string.
            output_dir (str): output dir string.
            test_type (str): test type string. Defaults to ``'unit'``.

        Returns:
            list[GeneratedTest]: a sequence of GeneratedTest entries (empty when there is nothing to
                report).

        Note:
            Coroutine - must be awaited.
        """
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
                tests.append(
                    GeneratedTest(
                        name=f"test_{cls['name'].lower()}",
                        code=test_code,
                        file_path=str(test_file),
                        test_type=test_type,
                    )
                )

            for func in functions:
                test_code = await self._generate_function_tests(func, test_type)
                test_file = Path(output_dir) / f"test_{source.stem}.py"
                tests.append(
                    GeneratedTest(
                        name=f"test_{func['name'].lower()}",
                        code=test_code,
                        file_path=str(test_file),
                        test_type=test_type,
                    )
                )

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
            classes.append(
                {
                    "name": match.group(1),
                    "parent": match.group(2),
                }
            )
        return classes

    def _extract_functions(self, content: str) -> list[dict]:
        functions = []
        pattern = r"def\s+(\w+)\s*\(([^)]*)\)"
        for match in re.finditer(pattern, content):
            if not match.group(1).startswith("_"):
                functions.append(
                    {
                        "name": match.group(1),
                        "args": match.group(2),
                    }
                )
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
        return ""

    def _combine_tests(self, tests: list[GeneratedTest]) -> str:
        lines = ['""', "", "import pytest", ""]
        for test in tests:
            for line in test.code.split("\n"):
                if line.strip() and not line.startswith('"""') and not line.startswith("from "):
                    lines.append(line)
        return "\n".join(lines)
