"""
Search.

Public objects: ``ToolSearch``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ToolSearch:
    """
    Tool search.
    """

    def __init__(self) -> None:
        """
        Initialise a ToolSearch instance.
        """
        self._tools: dict[str, dict[str, Any]] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        category: str = "",
        parameters: dict = None,
    ) -> None:
        """
        Register tool.

        Args:
            name (str): name of the object.
            description (str): human readable description.
            category (str): category string. Defaults to ``''``.
            parameters (dict): mapping of parameters. Defaults to ``None``.
        """
        self._tools[name] = {
            "name": name,
            "description": description,
            "category": category,
            "parameters": parameters or {},
        }

    def search(
        self,
        query: str,
        category: str = "",
        limit: int = 10,
    ) -> list[dict]:
        """
        Search.

        Args:
            query (str): search query.
            category (str): category string. Defaults to ``''``.
            limit (int): maximum number of items to return. Defaults to ``10``.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        query_lower = query.lower()
        results = []

        for tool in self._tools.values():
            if category and tool["category"] != category:
                continue

            score = 0
            if query_lower in tool["name"].lower():
                score += 10
            if query_lower in tool["description"].lower():
                score += 5
            if query_lower in tool["category"].lower():
                score += 3

            if score > 0:
                results.append({**tool, "score": score})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def list_categories(self) -> list[str]:
        """
        List categories.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        categories = set()
        for tool in self._tools.values():
            if tool["category"]:
                categories.add(tool["category"])
        return sorted(categories)

    def get_tool(self, name: str) -> dict | None:
        """
        Return the tool.

        Args:
            name (str): name of the object.

        Returns:
            dict | None: a mapping of str, Any.
        """
        return self._tools.get(name)

    def list_all(self) -> list[dict]:
        """
        List all.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        return list(self._tools.values())
