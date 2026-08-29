"""Testing framework integration for Bahram Agent."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    """A test case."""

    name: str
    description: str = ""
    steps: list[dict] = field(default_factory=list)
    expected: str = ""
    status: str = "pending"


class TestRunner:
    """Run and manage tests."""

    def __init__(self) -> None:
        self._test_cases: dict[str, TestCase] = {}
        self._results: list[dict] = []

    def add_test(self, name: str, steps: list[dict], expected: str = "") -> TestCase:
        """Add a test case."""
        test = TestCase(
            name=name,
            steps=steps,
            expected=expected,
        )
        self._test_cases[name] = test
        return test

    async def run_test(self, name: str, executor: Any = None) -> dict:
        """Run a single test."""
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
            result["status"] = "failed"
            result["error"] = str(e)

        test.status = result["status"]
        self._results.append(result)
        return result

    async def _run_step(self, step: dict, executor: Any = None) -> dict:
        """Run a test step."""
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
        """Run all tests."""
        results = []
        for name in self._test_cases:
            result = await self.run_test(name, executor)
            results.append(result)
        return results

    def get_summary(self) -> dict[str, int]:
        """Get test summary."""
        passed = sum(1 for r in self._results if r["status"] == "passed")
        failed = sum(1 for r in self._results if r["status"] == "failed")
        return {
            "total": len(self._results),
            "passed": passed,
            "failed": failed,
        }

    def format_report(self) -> str:
        """Format test results as report."""
        summary = self.get_summary()
        lines = [
            "## Test Report",
            f"Total: {summary['total']} | Passed: {summary['passed']} | Failed: {summary['failed']}",
            "",
        ]

        for result in self._results:
            status_emoji = "✅" if result["status"] == "passed" else "❌"
            lines.append(f"{status_emoji} {result['name']}")
            if result.get("error"):
                lines.append(f"   Error: {result['error']}")

        return "\n".join(lines)
