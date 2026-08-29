"""Intelligent Auto-Complete for Bahram Agent."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Completion:
    """A completion suggestion."""

    text: str
    description: str = ""
    priority: int = 0
    category: str = ""


class AutoComplete:
    """Intelligent code and command auto-completion."""

    def __init__(self) -> None:
        self._history: list[str] = []
        self._patterns: dict[str, list[str]] = {
            "python": [
                "def ", "class ", "import ", "from ", "if ", "else:", "elif ",
                "for ", "while ", "try:", "except:", "finally:", "with ",
                "return ", "yield ", "raise ", "assert ", "pass",
                "print(", "len(", "range(", "str(", "int(", "float(",
            ],
            "javascript": [
                "function ", "const ", "let ", "var ", "if ", "else ",
                "for ", "while ", "return ", "import ", "export ",
                "class ", "async ", "await ", "try ", "catch ",
            ],
            "bash": [
                "ls", "cd", "pwd", "mkdir", "rm", "cp", "mv", "cat",
                "grep", "find", "echo", "export", "chmod", "chown",
                "git", "docker", "npm", "pip", "python",
            ],
        }

    def add_to_history(self, text: str) -> None:
        """Add text to history."""
        if text not in self._history:
            self._history.append(text)
            if len(self._history) > 1000:
                self._history = self._history[-1000:]

    def complete(
        self,
        text: str,
        language: str = "python",
        context: str = "",
    ) -> list[Completion]:
        """Get completions for text."""
        completions = []

        # Pattern-based completions
        patterns = self._patterns.get(language, [])
        for pattern in patterns:
            if pattern.lower().startswith(text.lower()):
                completions.append(Completion(
                    text=pattern,
                    description=f"Keyword",
                    priority=1,
                    category="keyword",
                ))

        # History-based completions
        for hist in reversed(self._history):
            if text.lower() in hist.lower() and hist != text:
                completions.append(Completion(
                    text=hist,
                    description="From history",
                    priority=2,
                    category="history",
                ))

        # Remove duplicates and sort
        seen = set()
        unique = []
        for c in sorted(completions, key=lambda x: x.priority, reverse=True):
            if c.text not in seen:
                seen.add(c.text)
                unique.append(c)

        return unique[:10]

    def complete_command(self, text: str) -> list[Completion]:
        """Complete shell command."""
        return self.complete(text, language="bash")

    def complete_import(self, text: str) -> list[Completion]:
        """Complete import statement."""
        completions = []
        common_modules = [
            "os", "sys", "json", "logging", "asyncio", "pathlib",
            "typing", "dataclasses", "datetime", "time", "re",
            "collections", "itertools", "functools", "hashlib",
        ]
        for module in common_modules:
            if module.startswith(text.split(".")[-1]):
                completions.append(Completion(
                    text=module,
                    description="Module",
                    priority=1,
                    category="import",
                ))
        return completions

    def complete_function(self, text: str, context: str = "") -> list[Completion]:
        """Complete function call."""
        completions = []
        common_functions = [
            "print()", "len()", "range()", "str()", "int()", "float()",
            "list()", "dict()", "set()", "tuple()", "type()",
            "isinstance()", "hasattr()", "getattr()", "setattr()",
        ]
        for func in common_functions:
            if func.lower().startswith(text.lower()):
                completions.append(Completion(
                    text=func,
                    description="Function",
                    priority=1,
                    category="function",
                ))
        return completions

    def get_suggestions(self, text: str) -> list[str]:
        """Get simple string suggestions."""
        completions = self.complete(text)
        return [c.text for c in completions]
