"""Search tools for finding files and content."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from bahram.tools.base import BaseTool

logger = logging.getLogger(__name__)


class GlobTool(BaseTool):
    """Tool for finding files by pattern."""

    @property
    def name(self) -> str:
        return "glob"

    @property
    def description(self) -> str:
        return """Find files matching a glob pattern.
Useful for finding files by name, extension, or pattern.
Supports standard glob patterns like **/*.py, src/**/*.ts, etc."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (default: current directory)",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """Find files matching a pattern."""
        pattern = kwargs.get("pattern", "")
        path = kwargs.get("path", ".")

        if not pattern:
            return "Error: No pattern provided"

        try:
            search_path = Path(path)
            matches = list(search_path.glob(pattern))

            if not matches:
                return f"No files found matching pattern: {pattern}"

            # Format results
            results = [str(m) for m in matches[:100]]  # Limit to 100 results

            output = f"Found {len(matches)} files:\n"
            output += "\n".join(results)

            if len(matches) > 100:
                output += f"\n... and {len(matches) - 100} more"

            return output

        except Exception as e:
            return f"Error searching files: {e}"


class GrepTool(BaseTool):
    """Tool for searching file contents."""

    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return """Search for content in files using regex patterns.
Returns matching files and line numbers.
Useful for finding code, variables, functions, or any text pattern."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (default: current directory)",
                },
                "include": {
                    "type": "string",
                    "description": "File pattern to include (e.g., '*.py')",
                },
                "exclude": {
                    "type": "string",
                    "description": "File pattern to exclude",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """Search for content in files."""
        import re

        pattern = kwargs.get("pattern", "")
        path = kwargs.get("path", ".")
        include = kwargs.get("include", None)
        exclude = kwargs.get("exclude", None)

        if not pattern:
            return "Error: No pattern provided"

        try:
            # Compile regex
            regex = re.compile(pattern, re.IGNORECASE)

            search_path = Path(path)
            matches = []

            # Walk through files
            for root, dirs, files in os.walk(search_path):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                for file in files:
                    # Apply include/exclude filters
                    if include and not file.endswith(include.replace("*", "")):
                        continue
                    if exclude and file.endswith(exclude.replace("*", "")):
                        continue

                    file_path = Path(root) / file

                    try:
                        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                            for line_num, line in enumerate(f, 1):
                                if regex.search(line):
                                    matches.append(
                                        f"{file_path}:{line_num}: {line.strip()[:100]}"
                                    )

                                    if len(matches) >= 100:
                                        break

                    except Exception:
                        continue

                    if len(matches) >= 100:
                        break

                if len(matches) >= 100:
                    break

            if not matches:
                return f"No matches found for pattern: {pattern}"

            output = f"Found {len(matches)} matches:\n"
            output += "\n".join(matches)

            return output

        except re.error as e:
            return f"Invalid regex pattern: {e}"
        except Exception as e:
            return f"Error searching content: {e}"
