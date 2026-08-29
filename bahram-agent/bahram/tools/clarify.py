"""Clarify tool for Bahram Agent."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ClarifyQuestion:
    """A clarification question."""

    question: str
    options: list[dict[str, str]] = field(default_factory=list)
    multi_select: bool = False
    allow_custom: bool = True


class ClarifyTool:
    """Ask user for clarification with multiple choice options."""

    def __init__(self) -> None:
        self._pending: Optional[ClarifyQuestion] = None

    def ask(
        self,
        question: str,
        options: list[str] = None,
        multi_select: bool = False,
    ) -> ClarifyQuestion:
        """Ask a clarification question."""
        formatted_options = []
        if options:
            for i, opt in enumerate(options, 1):
                formatted_options.append({
                    "index": str(i),
                    "label": opt,
                })

        self._pending = ClarifyQuestion(
            question=question,
            options=formatted_options,
            multi_select=multi_select,
        )
        return self._pending

    def render(self, question: ClarifyQuestion = None) -> str:
        """Render question for display."""
        q = question or self._pending
        if not q:
            return ""

        parts = [f"**{q.question}**\n"]

        if q.options:
            for opt in q.options:
                parts.append(f"  {opt['index']}. {opt['label']}")

        if q.multi_select:
            parts.append("\n(Multiple selections allowed - separate with commas)")

        if q.allow_custom:
            parts.append("\nOr type your own answer.")

        return "\n".join(parts)

    def parse_response(self, response: str) -> dict[str, Any]:
        """Parse user response."""
        if not self._pending:
            return {"error": "No pending question"}

        q = self._pending
        self._pending = None

        if not response.strip():
            return {"cancelled": True}

        # Check if it's a number selection
        if q.options:
            if q.multi_select:
                # Parse multiple selections
                parts = [p.strip() for p in response.split(",")]
                selections = []
                for part in parts:
                    if part.isdigit() and 1 <= int(part) <= len(q.options):
                        selections.append(q.options[int(part) - 1]["label"])
                    elif q.allow_custom:
                        selections.append(part)
                return {"selected": selections}
            else:
                # Single selection
                if response.isdigit() and 1 <= int(response) <= len(q.options):
                    return {"selected": q.options[int(response) - 1]["label"]}

        # Custom answer
        return {"selected": response}

    def has_pending(self) -> bool:
        """Check if there's a pending question."""
        return self._pending is not None
