"""
Explainer.

Public objects: ``CodeExplanation``, ``CodeExplainer``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CodeExplanation:
    """
    Code explanation.

    Attributes:
        line (int): numeric value for line.
        code (str): source code to execute.
        explanation (str): explanation string.
        complexity (str): complexity string.
        concepts (list[str]): collection of concepts.
    """

    line: int
    code: str
    explanation: str
    complexity: str
    concepts: list[str] = field(default_factory=list)


class CodeExplainer:
    """
    Code explainer.
    """

    def __init__(self) -> None:
        """
        Initialise a CodeExplainer instance.
        """
        # pattern -> (message template, names of the capture groups in order).
        # Order matters: "from X import Y" is listed before the generic
        # "import Y" rule, which would otherwise match the tail of a
        # from-import and swallow the more specific explanation.
        self._patterns: dict[str, tuple[str, tuple[str, ...]]] = {
            r"def\s+(\w+)\s*\(([^)]*)\)": (
                "Function definition named '{name}' with parameters: {params}",
                ("name", "params"),
            ),
            r"class\s+(\w+)\s*(?:\(([^)]*)\))?": (
                "Class definition named '{name}'{parent}",
                ("name", "parent"),
            ),
            r"if\s+(.+):": ("Conditional check: {condition}", ("condition",)),
            r"for\s+(\w+)\s+in\s+(.+)": (
                "Loop iterating over {iterable} with variable {var}",
                ("var", "iterable"),
            ),
            r"while\s+(.+):": ("While loop with condition: {condition}", ("condition",)),
            r"try:": ("Try block for error handling", ()),
            r"except\s+(\w+)": ("Exception handler for {exception}", ("exception",)),
            r"return\s+(.+)": ("Returns value: {value}", ("value",)),
            r"from\s+(\w+)\s+import\s+(\w+)": (
                "Imports {item} from {module}",
                ("module", "item"),
            ),
            r"import\s+(\w+)": ("Imports module: {module}", ("module",)),
            r"lambda\s+([^:]+):\s*(.+)": (
                "Anonymous function with parameter {param}",
                ("param", "body"),
            ),
            r"\[(.+)\s+for\s+(\w+)\s+in\s+(.+)\]": (
                "List comprehension creating {item} from {iterable}",
                ("item", "var", "iterable"),
            ),
            r"\{(.+):\s*(.+)\s+for\s+(\w+)\s+in\s+(.+)\}": (
                "Dictionary comprehension building {key}: {value} pairs",
                ("key", "value", "var", "iterable"),
            ),
            r"async\s+def\s+(\w+)": ("Asynchronous function definition: {name}", ("name",)),
            r"await\s+(.+)": ("Awaiting async operation: {operation}", ("operation",)),
        }

    async def explain(self, code: str) -> list[CodeExplanation]:
        """
        Explain.

        Args:
            code (str): source code to execute.

        Returns:
            list[CodeExplanation]: a sequence of CodeExplanation entries (empty when there is
                nothing to report).

        Note:
            Coroutine - must be awaited.
        """
        explanations = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            explanation = await self._explain_line(line.strip())
            if explanation:
                explanations.append(explanation)

        return explanations

    async def _explain_line(self, line: str) -> CodeExplanation | None:
        if not line or line.startswith("#"):
            return None

        for pattern, (template, group_names) in self._patterns.items():
            match = re.search(pattern, line)
            if match:
                fields = dict(zip(group_names, match.groups()))
                # Optional groups are None when they did not participate.
                if fields.get("parent"):
                    fields["parent"] = f" (inherits from {fields['parent']})"
                else:
                    fields["parent"] = ""
                explanation = template.format(**fields)
                concepts = self._extract_concepts(line)

                return CodeExplanation(
                    line=0,
                    code=line,
                    explanation=explanation,
                    complexity=self._assess_complexity(line),
                    concepts=concepts,
                )

        return CodeExplanation(
            line=0,
            code=line,
            explanation=f"Code: {line[:100]}",
            complexity="simple",
            concepts=[],
        )

    def _extract_concepts(self, line: str) -> list[str]:
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
        """
        Format explanations.

        Args:
            explanations (list[CodeExplanation]): collection of explanations.

        Returns:
            str: the rendered string.
        """
        if not explanations:
            return "No code to explain!"

        lines = ["## Code Explanation", ""]

        for exp in explanations:
            complexity_emoji = {"simple": "🟢", "moderate": "🟡", "complex": "🔴"}
            lines.append(f"### Line {exp.line}")
            lines.append(f"```{exp.code}```")
            lines.append(f"**Explanation:** {exp.explanation}")
            lines.append(
                f"**Complexity:** {complexity_emoji.get(exp.complexity, '⚪')} {exp.complexity}"
            )
            if exp.concepts:
                lines.append(f"**Concepts:** {', '.join(exp.concepts)}")
            lines.append("")

        return "\n".join(lines)
