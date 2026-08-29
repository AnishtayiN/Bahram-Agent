"""Web search tool for Bahram Agent."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class WebSearchTool:
    """Search the web."""

    def __init__(self) -> None:
        self._search_engine: str = "google"
        self._max_results: int = 10

    async def search(
        self,
        query: str,
        num_results: int = None,
        engine: str = None,
    ) -> list[dict]:
        """Search the web."""
        try:
            import httpx

            # Use DuckDuckGo Instant Answers API (no key required)
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.duckduckgo.com/",
                    params={
                        "q": query,
                        "format": "json",
                        "no_html": 1,
                        "skip_disambig": 1,
                    },
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    results = []

                    # Abstract
                    if data.get("Abstract"):
                        results.append({
                            "title": data.get("Heading", ""),
                            "content": data["Abstract"],
                            "url": data.get("AbstractURL", ""),
                        })

                    # Related topics
                    for topic in data.get("RelatedTopics", [])[:num_results or self._max_results]:
                        if isinstance(topic, dict) and "Text" in topic:
                            results.append({
                                "title": topic.get("Text", "")[:100],
                                "content": topic.get("Text", ""),
                                "url": topic.get("FirstURL", ""),
                            })

                    return results
                else:
                    return [{"error": f"Search failed: HTTP {response.status_code}"}]

        except ImportError:
            return [{"error": "httpx not installed"}]
        except Exception as e:
            return [{"error": str(e)}]

    async def search_and_summarize(self, query: str) -> str:
        """Search and return summarized results."""
        results = await self.search(query, num_results=5)

        if not results:
            return "No results found"

        lines = [f"Search results for: {query}", ""]
        for i, result in enumerate(results, 1):
            if "error" in result:
                lines.append(f"{i}. Error: {result['error']}")
            else:
                lines.append(f"{i}. {result.get('title', 'Untitled')}")
                lines.append(f"   {result.get('content', '')[:200]}")
                lines.append(f"   URL: {result.get('url', '')}")
                lines.append("")

        return "\n".join(lines)

    def set_search_engine(self, engine: str) -> None:
        """Set search engine."""
        self._search_engine = engine

    def set_max_results(self, max_results: int) -> None:
        """Set max results."""
        self._max_results = max_results
