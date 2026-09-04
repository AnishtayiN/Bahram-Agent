"""
Complexity.

Public objects: ``ComplexityMetric``, ``ComplexityAnalyzer``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ComplexityMetric:
    """
    Complexity metric.

    Attributes:
        name (str): name of the object.
        value (float): numeric value for value.
        threshold (float): numeric value for threshold.
        status (str): status string.
        description (str): human readable description.
    """

    name: str
    value: float
    threshold: float
    status: str
    description: str = ""


class ComplexityAnalyzer:
    """
    Complexity analyzer.
    """

    def __init__(self) -> None:
        """
        Initialise a ComplexityAnalyzer instance.
        """
        self._thresholds = {
            "cyclomatic": {"good": 10, "warning": 20, "critical": 30},
            "cognitive": {"good": 15, "warning": 25, "critical": 50},
            "lines_per_function": {"good": 30, "warning": 50, "critical": 100},
            "parameters_per_function": {"good": 3, "warning": 5, "critical": 8},
            "nesting_depth": {"good": 3, "warning": 5, "critical": 8},
        }

    async def analyze(self, file_path: str) -> dict[str, Any]:
        """
        Analyze.

        Args:
            file_path (str): path of the file to operate on.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                content = f.read()

            metrics = {
                "cyclomatic": self._cyclomatic_complexity(content),
                "cognitive": self._cognitive_complexity(content),
                "lines_per_function": self._avg_lines_per_function(content),
                "parameters_per_function": self._avg_params_per_function(content),
                "nesting_depth": self._max_nesting_depth(content),
            }

            scores = []
            for name, value in metrics.items():
                threshold = self._thresholds.get(name, {})
                if value <= threshold.get("good", 100):
                    scores.append(100)
                elif value <= threshold.get("warning", 100):
                    scores.append(70)
                else:
                    scores.append(30)

            overall_score = sum(scores) / len(scores) if scores else 0

            return {
                "file": file_path,
                "metrics": metrics,
                "overall_score": overall_score,
                "rating": "A"
                if overall_score >= 90
                else "B"
                if overall_score >= 70
                else "C"
                if overall_score >= 50
                else "D",
            }

        except Exception as e:
            logger.warning(f"Failed to analyze {file_path}: {e}")
            return {"error": str(e)}

    def _cyclomatic_complexity(self, code: str) -> int:

        patterns = [
            r"\bif\b",
            r"\belif\b",
            r"\belse\b",
            r"\bfor\b",
            r"\bwhile\b",
            r"\band\b",
            r"\bor\b",
            r"\bexcept\b",
            r"\btry\b",
        ]
        complexity = 1
        for pattern in patterns:
            complexity += len(re.findall(pattern, code))
        return complexity

    def _cognitive_complexity(self, code: str) -> int:
        complexity = 0
        nesting = 0
        for line in code.split("\n"):
            stripped = line.strip()
            if any(
                stripped.startswith(kw)
                for kw in ["if", "elif", "else", "for", "while", "try", "except"]
            ):
                complexity += 1 + nesting
                nesting += 1
            elif stripped.startswith("return") or stripped.startswith("break"):
                complexity += 1
            elif nesting > 0 and not stripped.startswith(" ") and not stripped.startswith("#"):
                nesting -= 1
        return complexity

    def _avg_lines_per_function(self, code: str) -> float:
        functions = re.findall(r"def\s+\w+\s*\([^)]*\):", code)
        if not functions:
            return 0

        total_lines = len(code.split("\n"))
        return total_lines / len(functions)

    def _avg_params_per_function(self, code: str) -> float:
        params = re.findall(r"def\s+\w+\s*\(([^)]*)\)", code)
        if not params:
            return 0

        total_params = sum(len(p.split(",")) for p in params if p.strip())
        return total_params / len(params)

    def _max_nesting_depth(self, code: str) -> int:
        max_depth = 0
        current_depth = 0
        for line in code.split("\n"):
            stripped = line.strip()
            if any(
                stripped.startswith(kw)
                for kw in ["if", "elif", "else", "for", "while", "try", "except", "with"]
            ):
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif stripped and not stripped.startswith(" ") and not stripped.startswith("#"):
                current_depth = 0
        return max_depth

    def get_report(self, analysis: dict) -> str:
        """
        Return the report.

        Args:
            analysis (dict): mapping of analysis.

        Returns:
            str: the rendered string.
        """
        if "error" in analysis:
            return f"Error: {analysis['error']}"

        lines = ["## Code Complexity Report", ""]
        lines.append(f"**File:** {analysis['file']}")
        lines.append(f"**Rating:** {analysis['rating']} ({analysis['overall_score']:.0f}/100)")
        lines.append("")

        for name, value in analysis.get("metrics", {}).items():
            threshold = self._thresholds.get(name, {})
            if value <= threshold.get("good", 100):
                status = "✅ Good"
            elif value <= threshold.get("warning", 100):
                status = "⚠️ Warning"
            else:
                status = "🔴 Critical"
            lines.append(f"- **{name}:** {value:.1f} - {status}")

        return "\n".join(lines)
