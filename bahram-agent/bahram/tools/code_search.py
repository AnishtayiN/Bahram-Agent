"""Intelligent Code Search Engine for Bahram Agent."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A search result."""

    file: str
    line: int
    content: str
    score: float
    context: str = ""


class CodeSearchEngine:
    """Intelligent code search with semantic understanding."""

    def __init__(self) -> None:
        self._indexes: dict[str, list[dict]] = {}

    async def index_directory(self, dir_path: str) -> int:
        """Index a directory for search."""
        path = Path(dir_path)
        count = 0

        for file_path in path.rglob("*.py"):
            try:
                content = file_path.read_text(errors="replace")
                self._indexes[str(file_path)] = [
                    {"line": i + 1, "content": line}
                    for i, line in enumerate(content.split("\n"))
                ]
                count += 1
            except Exception as e:
                logger.warning(f"Failed to index {file_path}: {e}")

        return count

    async def search(
        self,
        query: str,
        file_pattern: str = None,
        max_results: int = 20,
    ) -> list[SearchResult]:
        """Search code with intelligent matching."""
        results = []
        query_lower = query.lower()

        for file_path, lines in self._indexes.items():
            # Apply file pattern filter
            if file_pattern and not re.search(file_pattern, file_path):
                continue

            for line_info in lines:
                content = line_info["content"]
                content_lower = content.lower()

                # Calculate relevance score
                score = 0.0

                # Exact match
                if query_lower in content_lower:
                    score += 1.0

                # Word boundary match
                if re.search(r'\b' + re.escape(query_lower) + r'\b', content_lower):
                    score += 0.5

                # Function/class name match
                if re.search(rf'(def|class)\s+{re.escape(query_lower)}', content_lower):
                    score += 0.8

                # Variable name match
                if re.search(rf'\b{re.escape(query_lower)}\s*=', content_lower):
                    score += 0.3

                if score > 0:
                    # Get context (2 lines before and after)
                    start = max(0, line_info["line"] - 3)
                    end = min(len(lines), line_info["line"] + 2)
                    context = "\n".join(l["content"] for l in lines[start:end])

                    results.append(SearchResult(
                        file=file_path,
                        line=line_info["line"],
                        content=content.strip(),
                        score=score,
                        context=context,
                    ))

        # Sort by score
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:max_results]

    async def find_definitions(self, name: str) -> list[SearchResult]:
        """Find function/class definitions."""
        results = []

        for file_path, lines in self._indexes.items():
            for line_info in lines:
                content = line_info["content"]
                if re.search(rf'(def|class)\s+{re.escape(name)}\s*\(', content):
                    results.append(SearchResult(
                        file=file_path,
                        line=line_info["line"],
                        content=content.strip(),
                        score=1.0,
                    ))

        return results

    async def find_references(self, name: str) -> list[SearchResult]:
        """Find references to a name."""
        results = []

        for file_path, lines in self._indexes.items():
            for line_info in lines:
                content = line_info["content"]
                if re.search(rf'\b{re.escape(name)}\b', content):
                    results.append(SearchResult(
                        file=file_path,
                        line=line_info["line"],
                        content=content.strip(),
                        score=0.5,
                    ))

        return results

    def format_results(self, results: list[SearchResult]) -> str:
        """Format search results."""
        if not results:
            return "No results found!"

        lines = ["## Search Results", ""]
        for r in results[:10]:
            lines.append(f"**{r.file}:{r.line}** (score: {r.score:.2f})")
            lines.append(f"```{r.content}```")
            lines.append("")

        return "\n".join(lines)
