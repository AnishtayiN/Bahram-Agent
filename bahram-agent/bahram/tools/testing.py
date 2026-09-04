"""
Testing.

Public objects: ``TestCase``, ``TestRunner``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    """
    Test case.

    Attributes:
        name (str): name of the object.
        description (str): human readable description.
        steps (list[dict]): collection of steps.
        expected (str): expected string.
        status (str): status string.
    """

    name: str
    description: str = ""
    steps: list[dict] = field(default_factory=list)
    expected: str = ""
    status: str = "pending"


class TestRunner:
    """
    Test runner.
    """

    def __init__(self) -> None:
        """
        Initialise a TestRunner instance.
        """
        self._test_cases: dict[str, TestCase] = {}
        self._results: list[dict] = []

    def add_test(self, name: str, steps: list[dict], expected: str = "") -> TestCase:
        """
        Add test.

        Args:
            name (str): name of the object.
            steps (list[dict]): collection of steps.
            expected (str): expected string. Defaults to ``''``.

        Returns:
            TestCase: the resulting TestCase.
        """
        test = TestCase(
            name=name,
            steps=steps,
            expected=expected,
        )
        self._test_cases[name] = test
        return test

    async def run_test(self, name: str, executor: Any = None) -> dict:
        """
        Run test.

        Args:
            name (str): name of the object.
            executor (Any): executor. Defaults to ``None``.

        Returns:
            dict: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        test = self._test_cases.get(name)
        if not test:
            return {"error": f"Test '{name}' not found"}

        test.status = "running"
        result = {"name": name, "status": "passed", "steps": []}

        try:
            for step in test.steps:
                step_result = await self._run_step(step, executor)
                result["steps"].append(step_result)
                if step_result.get("status") == "failed":
                    result["status"] = "failed"
                    break
        except Exception as e:
            logger.error("Test step failed: %s", e, exc_info=True)
            result["status"] = "failed"
            result["error"] = str(e)

        test.status = result["status"]
        self._results.append(result)
        return result

    async def _run_step(self, step: dict, executor: Any = None) -> dict:
        action = step.get("action", "")
        expected = step.get("expected", "")

        try:
            if executor:
                if hasattr(executor, action):
                    result = getattr(executor, action)(**step.get("params", {}))
                    if asyncio.iscoroutine(result):
                        result = await result
                else:
                    result = f"Action '{action}' not found"
            else:
                result = f"No executor for action '{action}'"

            passed = str(result) == expected if expected else True
            return {
                "action": action,
                "status": "passed" if passed else "failed",
                "result": str(result)[:200],
                "expected": expected,
            }
        except Exception as e:
            return {
                "action": action,
                "status": "failed",
                "error": str(e),
            }

    async def run_all(self, executor: Any = None) -> list[dict]:
        """
        Run all.

        Args:
            executor (Any): executor. Defaults to ``None``.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).

        Note:
            Coroutine - must be awaited.
        """
        results = []
        for name in self._test_cases:
            result = await self.run_test(name, executor)
            results.append(result)
        return results

    def get_summary(self) -> dict[str, int]:
        """
        Return the summary.

        Returns:
            dict[str, int]: a mapping of str, int.
        """
        passed = sum(1 for r in self._results if r["status"] == "passed")
        failed = sum(1 for r in self._results if r["status"] == "failed")
        return {
            "total": len(self._results),
            "passed": passed,
            "failed": failed,
        }

    def format_report(self) -> str:
        """
        Format report.

        Returns:
            str: the rendered string.
        """
        summary = self.get_summary()
        lines = [
            "## Test Report",
            (
                f"Total: {summary['total']} | Passed: {summary['passed']} | Failed: "
                f"{summary['failed']}"
            ),
            "",
        ]

        for result in self._results:
            status_emoji = "✅" if result["status"] == "passed" else "❌"
            lines.append(f"{status_emoji} {result['name']}")
            if result.get("error"):
                lines.append(f"   Error: {result['error']}")

        return "\n".join(lines)
