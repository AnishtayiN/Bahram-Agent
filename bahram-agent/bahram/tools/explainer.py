"""Intelligent Code Explanation Tool for Bahram Agent."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CodeExplanation:
    """Code explanation."""

    line: int
    code: str
    explanation: str
    complexity: str  # simple, moderate, complex
    concepts: list[str] = field(default_factory=list)


class CodeExplainer:
    """Intelligent code explanation and learning."""

    def __init__(self) -> None:
        self._patterns: dict[str, str] = {
            r"def\s+(\w+)\s*\(([^)]*)\)": "Function definition named '{name}' with parameters: {params}",
            r"class\s+(\w+)\s*(?:\(([^)]*)\))?": "Class definition named '{name}'{parent}",
            r"if\s+(.+):": "Conditional check: {condition}",
            r"for\s+(\w+)\s+in\s+(.+)": "Loop iterating over {iterable} with variable {var}",
            r"while\s+(.+):": "While loop with condition: {condition}",
            r"try:": "Try block for error handling",
            r"except\s+(\w+)": "Exception handler for {exception}",
            r"return\s+(.+)": "Returns value: {value}",
            r"import\s+(\w+)": "Imports module: {module}",
            r"from\s+(\w+)\s+import\s+(\w+)": "Imports {item} from {module}",
            r"lambda\s+([^:]+):\s*(.+)": "Anonymous function with parameter {param}",
            r"\[(.+)\s+for\s+(\w+)\s+in\s+(.+)\]": "List comprehension creating {item} from {iterable}",
            r"\{(.+):\s*(.+)\s+for\s+(\w+)\s+in\s+(.+)\}": "Dictionary comprehension",
            r"async\s+def\s+(\w+)": "Asynchronous function definition: {name}",
            r"await\s+(.+)": "Awaiting async operation: {operation}",
        }

    async def explain(self, code: str) -> list[CodeExplanation]:
        """Explain code line by line."""
        explanations = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            explanation = await self._explain_line(line.strip())
            if explanation:
                explanations.append(explanation)

        return explanations

    async def _explain_line(self, line: str) -> Optional[CodeExplanation]:
        """Explain a single line of code."""
        if not line or line.startswith("#"):
            return None

        # Find matching pattern
        for pattern, template in self._patterns.items():
            match = re.search(pattern, line)
            if match:
                # Extract named groups or use match groups
                explanation = template
                concepts = self._extract_concepts(line)

                return CodeExplanation(
                    line=0,
                    code=line,
                    explanation=explanation,
                    complexity=self._assess_complexity(line),
                    concepts=concepts,
                )

        # Default explanation
        return CodeExplanation(
            line=0,
            code=line,
            explanation=f"Code: {line[:100]}",
            complexity="simple",
            concepts=[],
        )

    def _extract_concepts(self, line: str) -> list[str]:
        """Extract programming concepts from line."""
        concepts = []
        if "def " in line:
            concepts.append("function")
        if "class " in line:
            concepts.append("class")
        if "if " in line:
            concepts.append("conditional")
        if "for " in line:
            concepts.append("loop")
        if "while " in line:
            concepts.append("loop")
        if "try" in line or "except" in line:
            concepts.append("error handling")
        if "async" in line or "await" in line:
            concepts.append("asynchronous")
        if "return" in line:
            concepts.append("return")
        if "import" in line:
            concepts.append("module")
        if "lambda" in line:
            concepts.append("functional")
        if "list comprehension" in line.lower() or "[..." in line:
            concepts.append("comprehension")
        return concepts

    def _assess_complexity(self, line: str) -> str:
        """Assess code complexity."""
        complex_patterns = [r"lambda", r"async", r"await", r"with", r"yield"]
        moderate_patterns = [r"for", r"while", r"if.*else", r"try"]

        for pattern in complex_patterns:
            if re.search(pattern, line):
                return "complex"

        for pattern in moderate_patterns:
            if re.search(pattern, line):
                return "moderate"

        return "simple"

    def format_explanations(self, explanations: list[CodeExplanation]) -> str:
        """Format explanations as report."""
        if not explanations:
            return "No code to explain!"

        lines = ["## Code Explanation", ""]

        for exp in explanations:
            complexity_emoji = {"simple": "🟢", "moderate": "🟡", "complex": "🔴"}
            lines.append(f"### Line {exp.line}")
            lines.append(f"```{exp.code}```")
            lines.append(f"**Explanation:** {exp.explanation}")
            lines.append(f"**Complexity:** {complexity_emoji.get(exp.complexity, '⚪')} {exp.complexity}")
            if exp.concepts:
                lines.append(f"**Concepts:** {', '.join(exp.concepts)}")
            lines.append("")

        return "\n".join(lines)
