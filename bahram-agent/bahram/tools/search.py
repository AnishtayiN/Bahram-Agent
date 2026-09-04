from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

class ToolSearch:

    def __init__(self) -> None:
        self._tools: dict[str, dict[str, Any]] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        category: str = "",
        parameters: dict = None,
    ) -> None:
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
        categories = set()
        for tool in self._tools.values():
            if tool["category"]:
                categories.add(tool["category"])
        return sorted(categories)

    def get_tool(self, name: str) -> dict | None:
        return self._tools.get(name)

    def list_all(self) -> list[dict]:
        return list(self._tools.values())
