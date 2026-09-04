from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class FormatRule:

    name: str
    language: str
    pattern: str
    replacement: str
    description: str = ""

class SmartFormatter:

    def __init__(self) -> None:
        self._rules: dict[str, list[FormatRule]] = {
            "python": [
                FormatRule("trailing_whitespace", "python", r"[ \t]+$", "", "Remove trailing whitespace"),
                FormatRule("blank_lines", "python", r"\n{3,}", "\n\n", "Max 2 blank lines"),
                FormatRule("import_order", "python", r"^(import|from)", "", "Import ordering"),
                FormatRule("line_length", "python", r".{80,}", "", "Line length check"),
            ],
            "javascript": [
                FormatRule("semicolons", "javascript", r"([^;])\s*$", r"\1;", "Add semicolons"),
                FormatRule("single_quotes", "javascript", r'"([^"]*)"', r"'\1'", "Use single quotes"),
                FormatRule("trailing_comma", "javascript", r",\s*}", "}", "Remove trailing commas"),
            ],
            "typescript": [
                FormatRule("semicolons", "typescript", r"([^;])\s*$", r"\1;", "Add semicolons"),
                FormatRule("single_quotes", "typescript", r'"([^"]*)"', r"'\1'", "Use single quotes"),
                FormatRule("type_annotations", "typescript", r":\s*(any)", "", "Avoid 'any' type"),
            ],
        }

    async def format(
        self,
        code: str,
        language: str,
        rules: list[str] = None,
    ) -> tuple[str, list[dict]]:
        rules_list = self._rules.get(language, [])
        if rules:
            rules_list = [r for r in rules_list if r.name in rules]

        formatted = code
        changes = []

        for rule in rules_list:
            new_formatted = re.sub(rule.pattern, rule.replacement, formatted, flags=re.MULTILINE)
            if new_formatted != formatted:
                changes.append({
                    "rule": rule.name,
                    "description": rule.description,
                    "count": len(re.findall(rule.pattern, formatted)),
                })
                formatted = new_formatted

        return formatted, changes

    async def check_style(self, code: str, language: str) -> list[dict]:
        rules_list = self._rules.get(language, [])
        issues = []

        for rule in rules_list:
            matches = re.findall(rule.pattern, code, re.MULTILINE)
            if matches:
                issues.append({
                    "rule": rule.name,
                    "description": rule.description,
                    "count": len(matches),
                })

        return issues

    def get_rules(self, language: str) -> list[dict]:
        rules = self._rules.get(language, [])
        return [
            {
                "name": r.name,
                "description": r.description,
                "pattern": r.pattern,
            }
            for r in rules
        ]

    def add_rule(self, rule: FormatRule) -> None:
        if rule.language not in self._rules:
            self._rules[rule.language] = []
        self._rules[rule.language].append(rule)
