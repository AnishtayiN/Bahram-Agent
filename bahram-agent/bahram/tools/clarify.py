"""
Clarify.

Public objects: ``ClarifyTool``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ClarifyTool:
    """
    Clarify tool.
    """

    def __init__(self) -> None:
        """
        Initialise a ClarifyTool instance.
        """
        self._pending_clarifications: dict[str, dict] = {}
        self._clarification_history: list[dict] = []

    async def request_clarification(
        self,
        question: str,
        context: str = "",
        options: list[str] = None,
        required: bool = True,
    ) -> dict[str, Any]:
        """
        Request clarification.

        Args:
            question (str): question string.
            context (str): context string. Defaults to ``''``.
            options (list[str]): collection of options. Defaults to ``None``.
            required (bool): when ``True``, enable required. Defaults to ``True``.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        import time
        import uuid

        clarification_id = f"clarify_{uuid.uuid4().hex[:8]}"

        self._pending_clarifications[clarification_id] = {
            "question": question,
            "context": context,
            "options": options,
            "required": required,
            "timestamp": time.time(),
        }

        return {
            "clarification_id": clarification_id,
            "question": question,
            "context": context,
            "options": options,
            "required": required,
        }

    def get_clarification(self, clarification_id: str) -> dict | None:
        """
        Return the clarification.

        Args:
            clarification_id (str): clarification id string.

        Returns:
            dict | None: a mapping of str, Any.
        """
        return self._pending_clarifications.get(clarification_id)

    def answer_clarification(
        self,
        clarification_id: str,
        answer: str,
    ) -> bool:
        """
        Answer clarification.

        Args:
            clarification_id (str): clarification id string.
            answer (str): answer string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        if clarification_id in self._pending_clarifications:
            clarification = self._pending_clarifications.pop(clarification_id)
            self._clarification_history.append(
                {
                    "question": clarification["question"],
                    "answer": answer,
                    "timestamp": clarification["timestamp"],
                }
            )
            return True
        return False

    def has_pending(self) -> bool:
        """
        Return ``True`` when the object has pending.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        return len(self._pending_clarifications) > 0

    def get_pending_count(self) -> int:
        """
        Return the pending count.

        Returns:
            int: the computed numeric value.
        """
        return len(self._pending_clarifications)

    def get_history(self) -> list[dict]:
        """
        Return the history.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        return self._clarification_history.copy()

    def clear_pending(self) -> int:
        """
        Clear pending.

        Returns:
            int: the computed numeric value.
        """
        count = len(self._pending_clarifications)
        self._pending_clarifications.clear()
        return count
