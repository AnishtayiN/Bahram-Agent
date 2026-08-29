from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class CompletionContext:
    ""

    file_path: str
    line: int
    column: int
    language: str
    code_before: str
    code_after: str = ""

class SmartCodeCompletion:
    ""

    def __init__(self) -> None:
        self._snippets: dict[str, list[dict]] = {
            "python": [
                {"trigger": "def", "snippet": "def ${1:name}(${2:args}):\n    ${3:pass}", "description": "Function definition"},
                {"trigger": "class", "snippet": "class ${1:name}:\n    def __init__(self${2:args}):\n        ${3:pass}", "description": "Class definition"},
                {"trigger": "if", "snippet": "if ${1:condition}:\n    ${2:pass}", "description": "If statement"},
                {"trigger": "for", "snippet": "for ${1:item} in ${2:iterable}:\n    ${3:pass}", "description": "For loop"},
                {"trigger": "try", "snippet": "try:\n    ${1:pass}\nexcept ${2:Exception} as e:\n    ${3:pass}", "description": "Try/except block"},
                {"trigger": "async", "snippet": "async def ${1:name}(${2:args}):\n    ${3:pass}", "description": "Async function"},
                {"trigger": "with", "snippet": "with ${1:expression} as ${2:var}:\n    ${3:pass}", "description": "With statement"},
            ],
            "javascript": [
                {"trigger": "fn", "snippet": "function ${1:name}(${2:args}) {\n    ${3:// body}\n}", "description": "Function"},
                {"trigger": "afn", "snippet": "const ${1:name} = async (${2:args}) => {\n    ${3:// body}\n}", "description": "Async function"},
                {"trigger": "if", "snippet": "if (${1:condition}) {\n    ${2:// body}\n}", "description": "If statement"},
                {"trigger": "for", "snippet": "for (let ${1:i} = 0; ${1:i} < ${2:length}; ${1:i}++) {\n    ${3:// body}\n}", "description": "For loop"},
                {"trigger": "cls", "snippet": "class ${1:name} {\n    constructor(${2:args}) {\n        ${3:// body}\n    }\n}", "description": "Class"},
            ],
            "typescript": [
                {"trigger": "fn", "snippet": "function ${1:name}(${2:args}): ${3:void} {\n    ${4:// body}\n}", "description": "Function"},
                {"trigger": "afn", "snippet": "const ${1:name} = async (${2:args}): Promise<${3:void}> => {\n    ${4:// body}\n}", "description": "Async function"},
                {"trigger": "int", "snippet": "interface ${1:name} {\n    ${2:// properties}\n}", "description": "Interface"},
                {"trigger": "type", "snippet": "type ${1:name} = ${2:type};", "description": "Type alias"},
            ],
        }

    def complete(
        self,
        context: CompletionContext,
        trigger: str = "",
    ) -> list[dict]:
        ""
        completions = []
        language = context.language

        snippets = self._snippets.get(language, [])

        for snippet in snippets:
            if trigger and not snippet["trigger"].startswith(trigger):
                continue

            completions.append({
                "text": snippet["snippet"],
                "description": snippet["description"],
                "trigger": snippet["trigger"],
                "priority": 1 if trigger and snippet["trigger"] == trigger else 0,
            })

        context_completions = self._get_context_completions(context)
        completions.extend(context_completions)

        return sorted(completions, key=lambda x: x["priority"], reverse=True)

    def _get_context_completions(self, context: CompletionContext) -> list[dict]:
        ""
        completions = []
        lines = context.code_before.split("\n")

        if lines:
            last_line = lines[-1].strip()

            if last_line.startswith("import ") or last_line.startswith("from "):
                completions.extend(self._get_import_completions(context))

            if last_line.startswith("def ") or last_line.startswith("class "):
                completions.extend(self._get_definition_completions(context))

            if len(lines) > 1 and last_line.startswith("    "):
                completions.extend(self._get_function_body_completions(context))

        return completions

    def _get_import_completions(self, context: CompletionContext) -> list[dict]:
        ""
        common_imports = [
            "os", "sys", "json", "logging", "asyncio", "pathlib",
            "typing", "dataclasses", "datetime", "time", "re",
            "collections", "itertools", "functools", "hashlib",
            "httpx", "pydantic", "fastapi", "uvicorn",
        ]
        return [
            {"text": imp, "description": "Import", "priority": 1}
            for imp in common_imports
        ]

    def _get_definition_completions(self, context: CompletionContext) -> list[dict]:
        ""
        return [
            {"text": "def __init__(self):", "description": "Constructor", "priority": 1},
            {"text": "def __str__(self):", "description": "String representation", "priority": 1},
            {"text": "def __repr__(self):", "description": "Representation", "priority": 1},
        ]

    def _get_function_body_completions(self, context: CompletionContext) -> list[dict]:
        ""
        return [
            {"text": "return", "description": "Return statement", "priority": 1},
            {"text": "if condition:", "description": "If statement", "priority": 1},
            {"text": "for item in iterable:", "description": "For loop", "priority": 1},
        ]

    def get_snippet(self, language: str, trigger: str) -> Optional[str]:
        ""
        snippets = self._snippets.get(language, [])
        for snippet in snippets:
            if snippet["trigger"] == trigger:
                return snippet["snippet"]
        return None
