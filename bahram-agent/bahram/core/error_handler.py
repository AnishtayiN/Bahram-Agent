"""
Error handler.

Public objects: ``ErrorSolution``, ``ErrorHandler``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ErrorSolution:
    """
    Error solution.

    Attributes:
        error_type (str): error type string.
        solution (str): solution string.
        confidence (float): numeric value for confidence.
        steps (list[str]): collection of steps.
    """

    error_type: str
    solution: str
    confidence: float
    steps: list[str] = field(default_factory=list)


class ErrorHandler:
    """
    Error handler.
    """

    def __init__(self) -> None:
        """
        Initialise a ErrorHandler instance.
        """
        self._solutions: dict[str, list[ErrorSolution]] = {
            "ModuleNotFoundError": [
                ErrorSolution(
                    error_type="ModuleNotFoundError",
                    solution="Install the missing module",
                    confidence=0.95,
                    steps=["pip install <module_name>", "or add to requirements.txt"],
                ),
            ],
            "ImportError": [
                ErrorSolution(
                    error_type="ImportError",
                    solution="Check import path and module availability",
                    confidence=0.9,
                    steps=["Verify module exists", "Check spelling", "Install if missing"],
                ),
            ],
            "SyntaxError": [
                ErrorSolution(
                    error_type="SyntaxError",
                    solution="Fix Python syntax",
                    confidence=0.95,
                    steps=["Check parentheses/brackets", "Check indentation", "Check colons"],
                ),
            ],
            "IndentationError": [
                ErrorSolution(
                    error_type="IndentationError",
                    solution="Fix indentation",
                    confidence=0.95,
                    steps=["Use consistent indentation (4 spaces)", "Check mixed tabs/spaces"],
                ),
            ],
            "TypeError": [
                ErrorSolution(
                    error_type="TypeError",
                    solution="Check function arguments and types",
                    confidence=0.85,
                    steps=[
                        "Check function signature",
                        "Verify argument types",
                        "Check return values",
                    ],
                ),
            ],
            "ValueError": [
                ErrorSolution(
                    error_type="ValueError",
                    solution="Check input values",
                    confidence=0.85,
                    steps=["Validate input data", "Check range/format", "Add error handling"],
                ),
            ],
            "KeyError": [
                ErrorSolution(
                    error_type="KeyError",
                    solution="Check dictionary key",
                    confidence=0.9,
                    steps=["Verify key exists", "Use .get() method", "Check key spelling"],
                ),
            ],
            "FileNotFoundError": [
                ErrorSolution(
                    error_type="FileNotFoundError",
                    solution="Check file path",
                    confidence=0.95,
                    steps=["Verify file exists", "Check path spelling", "Use absolute path"],
                ),
            ],
            "PermissionError": [
                ErrorSolution(
                    error_type="PermissionError",
                    solution="Check file permissions",
                    confidence=0.9,
                    steps=["Check file permissions", "Run as admin", "Use chmod/chown"],
                ),
            ],
            "ConnectionError": [
                ErrorSolution(
                    error_type="ConnectionError",
                    solution="Check network connection",
                    confidence=0.85,
                    steps=["Verify network", "Check URL", "Check firewall/proxy"],
                ),
            ],
            "TimeoutError": [
                ErrorSolution(
                    error_type="TimeoutError",
                    solution="Increase timeout or optimize",
                    confidence=0.8,
                    steps=["Increase timeout value", "Optimize code", "Check network speed"],
                ),
            ],
        }

    def handle_error(self, error: Exception) -> ErrorSolution:
        """
        Handle error.

        Args:
            error (Exception): error.

        Returns:
            ErrorSolution: the resulting ErrorSolution.
        """
        error_type = type(error).__name__
        error_msg = str(error)

        solutions = self._solutions.get(error_type, [])
        if solutions:
            solution = solutions[0]

            solution.solution = f"{solution.solution}: {error_msg}"
            return solution

        return ErrorSolution(
            error_type=error_type,
            solution=f"Error: {error_msg}",
            confidence=0.5,
            steps=["Check the traceback", "Review the code", "Search for similar errors"],
        )

    def get_solution(self, error_type: str) -> ErrorSolution | None:
        """
        Return the solution.

        Args:
            error_type (str): error type string.

        Returns:
            ErrorSolution | None: the resulting object, or ``None`` when it is not available.
        """
        solutions = self._solutions.get(error_type, [])
        return solutions[0] if solutions else None

    def add_solution(self, solution: ErrorSolution) -> None:
        """
        Add solution.

        Args:
            solution (ErrorSolution): solution.
        """
        if solution.error_type not in self._solutions:
            self._solutions[solution.error_type] = []
        self._solutions[solution.error_type].append(solution)

    def format_error(self, error: Exception, solution: ErrorSolution = None) -> str:
        """
        Format error.

        Args:
            error (Exception): error.
            solution (ErrorSolution): solution. Defaults to ``None``.

        Returns:
            str: the rendered string.
        """
        lines = [
            f"**Error:** `{type(error).__name__}`",
            f"**Message:** {error}",
            "",
        ]

        if solution:
            lines.append(f"**Solution:** {solution.solution}")
            if solution.steps:
                lines.append("**Steps:**")
                for i, step in enumerate(solution.steps, 1):
                    lines.append(f"{i}. {step}")
            lines.append(f"**Confidence:** {solution.confidence:.0%}")

        return "\n".join(lines)

    def get_all_solutions(self) -> dict[str, list[str]]:
        """
        Return the all solutions.

        Returns:
            dict[str, list[str]]: a mapping of str, list[str].
        """
        return {
            error_type: [s.solution for s in solutions]
            for error_type, solutions in self._solutions.items()
        }
