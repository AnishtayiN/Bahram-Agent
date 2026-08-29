from __future__ import annotations

import logging
from typing import Any

from bahram.tools.base import BaseTool

logger = logging.getLogger(__name__)

class WebFetchTool(BaseTool):
    def __init__(self, config: Any = None) -> None:
        self.config = config
        self.timeout = getattr(config, "webfetch_timeout", 30) if config else 30
        self.max_size = getattr(config, "webfetch_max_size", 1048576) if config else 1048576

    @property
    def name(self) -> str:
        return "webfetch"

    @property
    def description(self) -> str:
        return "Fetch a URL and return its content as text, markdown, or HTML."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to fetch",
                },
                "format": {
                    "type": "string",
                    "enum": ["text", "markdown", "html"],
                    "description": "Output format (default: text)",
                },
            },
            "required": ["url"],
        }

    async def execute(self, **kwargs: Any) -> str:
        ""
        import httpx

        url = kwargs.get("url", "")
        format_type = kwargs.get("format", "text")

        if not url:
            return "Error: No URL provided"

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": "Bahram-Agent/1.0"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

                if len(response.content) > self.max_size:
                    return f"Error: Response too large ({len(response.content)} bytes)"

                if format_type == "html":
                    return response.text
                elif format_type == "markdown":

                    import re

                    text = response.text

                    text = re.sub(r"<[^>]+>", " ", text)

                    text = re.sub(r"\s+", " ", text).strip()
                    return text
                else:

                    try:
                        from readability import Document

                        doc = Document(response.text)
                        return doc.summary()
                    except ImportError:

                        import re

                        text = response.text
                        text = re.sub(r"<[^>]+>", " ", text)
                        text = re.sub(r"\s+", " ", text).strip()
                        return text[:5000]

        except httpx.TimeoutException:
            return f"Error: Request timed out after {self.timeout} seconds"
        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code}"
        except Exception as e:
            return f"Error fetching URL: {e}"

class WebSearchTool(BaseTool):
    def __init__(self, config: Any = None) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return "websearch"

    @property
    def description(self) -> str:
        return "Search the web using DuckDuckGo and return results."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return (default: 5)",
                },
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> str:
        ""
        import httpx

        query = kwargs.get("query", "")
        num_results = kwargs.get("num_results", 5)

        if not query:
            return "Error: No query provided"

        try:

            async with httpx.AsyncClient(timeout=30) as client:

                response = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Bahram-Agent/1.0"},
                )

                if response.status_code != 200:
                    return f"Error: Search failed with status {response.status_code}"

                import re

                html = response.text

                results = []
                result_pattern = re.compile(
                    r'<a[^>]+class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
                    r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
                    re.DOTALL,
                )

                for match in result_pattern.finditer(html):
                    if len(results) >= num_results:
                        break
                    url, title, snippet = match.groups()

                    title = re.sub(r"<[^>]+>", "", title).strip()
                    snippet = re.sub(r"<[^>]+>", "", snippet).strip()
                    results.append(f"**{title}**\n{url}\n{snippet}\n")

                if not results:
                    return f"No results found for: {query}"

                return f"Search results for '{query}':\n\n" + "\n".join(results)

        except Exception as e:
            return f"Error searching web: {e}"
