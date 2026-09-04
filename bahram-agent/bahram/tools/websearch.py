"""
Websearch.

Public objects: ``WebSearchTool``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class WebSearchTool:
    """
    Web search tool.
    """

    def __init__(self) -> None:
        """
        Initialise a WebSearchTool instance.
        """
        self._search_engine: str = "google"
        self._max_results: int = 10

    async def search(
        self,
        query: str,
        num_results: int = None,
        engine: str = None,
    ) -> list[dict]:
        """
        Search.

        Args:
            query (str): search query.
            num_results (int): numeric value for num results. Defaults to ``None``.
            engine (str): engine string. Defaults to ``None``.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).

        Note:
            Coroutine - must be awaited.
        """
        try:
            import httpx

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

                    if data.get("Abstract"):
                        results.append(
                            {
                                "title": data.get("Heading", ""),
                                "content": data["Abstract"],
                                "url": data.get("AbstractURL", ""),
                            }
                        )

                    for topic in data.get("RelatedTopics", [])[: num_results or self._max_results]:
                        if isinstance(topic, dict) and "Text" in topic:
                            results.append(
                                {
                                    "title": topic.get("Text", "")[:100],
                                    "content": topic.get("Text", ""),
                                    "url": topic.get("FirstURL", ""),
                                }
                            )

                    return results
                else:
                    return [{"error": f"Search failed: HTTP {response.status_code}"}]

        except ImportError:
            return [{"error": "httpx not installed"}]
        except Exception as e:
            return [{"error": str(e)}]

    async def search_and_summarize(self, query: str) -> str:
        """
        Search and summarize.

        Args:
            query (str): search query.

        Returns:
            str: the rendered string.

        Note:
            Coroutine - must be awaited.
        """
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
        """
        Set the search engine.

        Args:
            engine (str): engine string.
        """
        self._search_engine = engine

    def set_max_results(self, max_results: int) -> None:
        """
        Set the max results.

        Args:
            max_results (int): numeric value for max results.
        """
        self._max_results = max_results
