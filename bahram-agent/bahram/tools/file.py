from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from bahram.tools.base import BaseTool

logger = logging.getLogger(__name__)

_file_safety = None

def _get_file_safety():
    global _file_safety
    if _file_safety is None:
        try:
            from bahram.security.file_safety import FileWriteSafety
            _file_safety = FileWriteSafety()
        except Exception:
            pass
    return _file_safety

class ReadTool(BaseTool):
    @property
    def name(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return "Read a file and return its contents with line numbers."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to read",
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (0-based)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read",
                },
            },
            "required": ["file_path"],
        }

    async def execute(self, **kwargs: Any) -> str:
        file_path = kwargs.get("file_path", "")
        offset = kwargs.get("offset", 0)
        limit = kwargs.get("limit", 2000)

        if not file_path:
            return "Error: No file path provided"

        path = Path(file_path)

        if not path.exists():
            return f"Error: File not found: {file_path}"

        if not path.is_file():
            return f"Error: Not a file: {file_path}"

        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            lines = lines[offset : offset + limit]

            formatted = []
            for i, line in enumerate(lines, start=offset + 1):
                formatted.append(f"{i}: {line.rstrip()}")

            return "\n".join(formatted)

        except Exception as e:
            return f"Error reading file: {e}"

class WriteTool(BaseTool):
    @property
    def name(self) -> str:
        return "write"

    @property
    def description(self) -> str:
        return "Write content to a file, creating parent directories if needed."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
                "create_dirs": {
                    "type": "boolean",
                    "description": "Create parent directories if they don't exist",
                },
            },
            "required": ["file_path", "content"],
        }

    async def execute(self, **kwargs: Any) -> str:
        file_path = kwargs.get("file_path", "")
        content = kwargs.get("content", "")
        create_dirs = kwargs.get("create_dirs", True)

        if not file_path:
            return "Error: No file path provided"

        safety = _get_file_safety()
        if safety:
            safe, msg = safety.check_write(file_path)
            if not safe:
                return f"Error: {msg}"

        path = Path(file_path)

        try:
            if create_dirs:
                path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"Written to file: {file_path}")
            return f"Successfully wrote to {file_path}"
        except Exception as e:
            return f"Error writing file: {e}"

class EditTool(BaseTool):
    @property
    def name(self) -> str:
        return "edit"

    @property
    def description(self) -> str:
        return "Edit a file by replacing a specific string with a new string."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to edit",
                },
                "old_string": {
                    "type": "string",
                    "description": "The exact string to replace",
                },
                "new_string": {
                    "type": "string",
                    "description": "The string to replace it with",
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace all occurrences (default: false)",
                },
            },
            "required": ["file_path", "old_string", "new_string"],
        }

    async def execute(self, **kwargs: Any) -> str:
        file_path = kwargs.get("file_path", "")
        old_string = kwargs.get("old_string", "")
        new_string = kwargs.get("new_string", "")
        replace_all = kwargs.get("replace_all", False)

        if not file_path:
            return "Error: No file path provided"

        if not old_string:
            return "Error: No old_string provided"

        safety = _get_file_safety()
        if safety:
            safe, msg = safety.check_write(file_path)
            if not safe:
                return f"Error: {msg}"

        path = Path(file_path)

        if not path.exists():
            return f"Error: File not found: {file_path}"

        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()

            if old_string not in content:
                return f"Error: old_string not found in {file_path}"

            count = content.count(old_string)
            if count > 1 and not replace_all:
                return f"Error: Found {count} occurrences of old_string. Use replace_all or provide more context."

            if replace_all:
                new_content = content.replace(old_string, new_string)
            else:
                new_content = content.replace(old_string, new_string, 1)

            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)

            logger.info(f"Edited file: {file_path}")
            return f"Successfully edited {file_path}"

        except Exception as e:
            return f"Error editing file: {e}"
