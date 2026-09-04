"""
Smart completion.

Public objects: ``CompletionContext``, ``SmartCodeCompletion``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CompletionContext:
    """
    Completion context.

    Attributes:
        file_path (str): path of the file to operate on.
        line (int): numeric value for line.
        column (int): numeric value for column.
        language (str): language string.
        code_before (str): code before string.
        code_after (str): code after string.
    """

    file_path: str
    line: int
    column: int
    language: str
    code_before: str
    code_after: str = ""


class SmartCodeCompletion:
    """
    Smart code completion.
    """

    def __init__(self) -> None:
        """
        Initialise a SmartCodeCompletion instance.
        """
        self._snippets: dict[str, list[dict]] = {
            "python": [
                {
                    "trigger": "def",
                    "snippet": "def ${1:name}(${2:args}):\n    ${3:pass}",
                    "description": "Function definition",
                },
                {
                    "trigger": "class",
                    "snippet": (
                        "class ${1:name}:\n    def __init__(self${2:args}):\n        ${3:pass}"
                    ),
                    "description": "Class definition",
                },
                {
                    "trigger": "if",
                    "snippet": "if ${1:condition}:\n    ${2:pass}",
                    "description": "If statement",
                },
                {
                    "trigger": "for",
                    "snippet": "for ${1:item} in ${2:iterable}:\n    ${3:pass}",
                    "description": "For loop",
                },
                {
                    "trigger": "try",
                    "snippet": "try:\n    ${1:pass}\nexcept ${2:Exception} as e:\n    ${3:pass}",
                    "description": "Try/except block",
                },
                {
                    "trigger": "async",
                    "snippet": "async def ${1:name}(${2:args}):\n    ${3:pass}",
                    "description": "Async function",
                },
                {
                    "trigger": "with",
                    "snippet": "with ${1:expression} as ${2:var}:\n    ${3:pass}",
                    "description": "With statement",
                },
            ],
            "javascript": [
                {
                    "trigger": "fn",
                    "snippet": "function ${1:name}(${2:args}) {\n    ${3:// body}\n}",
                    "description": "Function",
                },
                {
                    "trigger": "afn",
                    "snippet": "const ${1:name} = async (${2:args}) => {\n    ${3:// body}\n}",
                    "description": "Async function",
                },
                {
                    "trigger": "if",
                    "snippet": "if (${1:condition}) {\n    ${2:// body}\n}",
                    "description": "If statement",
                },
                {
                    "trigger": "for",
                    "snippet": (
                        "for (let ${1:i} = 0; ${1:i} < ${2:length}; ${1:i}++) "
                        "{\n    ${3:// body}\n}"
                    ),
                    "description": "For loop",
                },
                {
                    "trigger": "cls",
                    "snippet": (
                        "class ${1:name} "
                        "{\n    constructor(${2:args}) {\n        ${3:// body}\n    }\n}"
                    ),
                    "description": "Class",
                },
            ],
            "typescript": [
                {
                    "trigger": "fn",
                    "snippet": "function ${1:name}(${2:args}): ${3:void} {\n    ${4:// body}\n}",
                    "description": "Function",
                },
                {
                    "trigger": "afn",
                    "snippet": (
                        "const ${1:name} = async (${2:args}): Promise<${3:void}> => "
                        "{\n    ${4:// body}\n}"
                    ),
                    "description": "Async function",
                },
                {
                    "trigger": "int",
                    "snippet": "interface ${1:name} {\n    ${2:// properties}\n}",
                    "description": "Interface",
                },
                {
                    "trigger": "type",
                    "snippet": "type ${1:name} = ${2:type};",
                    "description": "Type alias",
                },
            ],
        }

    def complete(
        self,
        context: CompletionContext,
        trigger: str = "",
    ) -> list[dict]:
        """
        Complete.

        Args:
            context (CompletionContext): context.
            trigger (str): trigger string. Defaults to ``''``.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        completions = []
        language = context.language

        snippets = self._snippets.get(language, [])

        for snippet in snippets:
            if trigger and not snippet["trigger"].startswith(trigger):
                continue

            completions.append(
                {
                    "text": snippet["snippet"],
                    "description": snippet["description"],
                    "trigger": snippet["trigger"],
                    "priority": 1 if trigger and snippet["trigger"] == trigger else 0,
                }
            )

        context_completions = self._get_context_completions(context)
        completions.extend(context_completions)

        return sorted(completions, key=lambda x: x["priority"], reverse=True)

    def _get_context_completions(self, context: CompletionContext) -> list[dict]:
        completions = []
        lines = context.code_before.split("\n")

        if lines:
            raw_line = lines[-1]
            last_line = raw_line.strip()

            # Compare on the first token: last_line has been stripped, so
            # "import " (with its trailing space) can never match
            # startswith("import ") and the branch was dead code.
            first_word = last_line.split()[0] if last_line.split() else ""
            if first_word in ("import", "from"):
                completions.extend(self._get_import_completions(context))

            if last_line.startswith("def ") or last_line.startswith("class "):
                completions.extend(self._get_definition_completions(context))

            # Indentation must be measured on the unstripped line - after
            # strip() no line can ever start with four spaces.
            if len(lines) > 1 and raw_line.startswith("    "):
                completions.extend(self._get_function_body_completions(context))

        return completions

    def _get_import_completions(self, context: CompletionContext) -> list[dict]:
        common_imports = [
            "os",
            "sys",
            "json",
            "logging",
            "asyncio",
            "pathlib",
            "typing",
            "dataclasses",
            "datetime",
            "time",
            "re",
            "collections",
            "itertools",
            "functools",
            "hashlib",
            "httpx",
            "pydantic",
            "fastapi",
            "uvicorn",
        ]
        return [{"text": imp, "description": "Import", "priority": 1} for imp in common_imports]

    def _get_definition_completions(self, context: CompletionContext) -> list[dict]:
        return [
            {"text": "def __init__(self):", "description": "Constructor", "priority": 1},
            {"text": "def __str__(self):", "description": "String representation", "priority": 1},
            {"text": "def __repr__(self):", "description": "Representation", "priority": 1},
        ]

    def _get_function_body_completions(self, context: CompletionContext) -> list[dict]:
        return [
            {"text": "return", "description": "Return statement", "priority": 1},
            {"text": "if condition:", "description": "If statement", "priority": 1},
            {"text": "for item in iterable:", "description": "For loop", "priority": 1},
        ]

    def get_snippet(self, language: str, trigger: str) -> str | None:
        """
        Return the snippet.

        Args:
            language (str): language string.
            trigger (str): trigger string.

        Returns:
            str | None: the resulting object, or ``None`` when it is not available.
        """
        snippets = self._snippets.get(language, [])
        for snippet in snippets:
            if snippet["trigger"] == trigger:
                return snippet["snippet"]
        return None
