"""Execute code tool for Bahram Agent."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ExecuteCodeTool:
    """Execute Python code safely."""

    def __init__(self) -> None:
        self._timeout: float = 30.0
        self._max_output: int = 10000
        self._allowed_modules: list[str] = []

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: float = None,
    ) -> dict[str, Any]:
        """Execute code."""
        if language == "python":
            return await self._execute_python(code, timeout)
        elif language == "bash":
            return await self._execute_bash(code, timeout)
        else:
            return {"error": f"Unsupported language: {language}"}

    async def _execute_python(self, code: str, timeout: float = None) -> dict[str, Any]:
        """Execute Python code."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "python3", temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout or self._timeout,
                )
                return {
                    "stdout": stdout.decode("utf-8", errors="replace")[:self._max_output],
                    "stderr": stderr.decode("utf-8", errors="replace")[:self._max_output],
                    "exit_code": proc.returncode,
                }
            except asyncio.TimeoutError:
                proc.kill()
                return {
                    "stdout": "",
                    "stderr": "Execution timed out",
                    "exit_code": -1,
                }
        finally:
            Path(temp_path).unlink(missing_ok=True)

    async def _execute_bash(self, code: str, timeout: float = None) -> dict[str, Any]:
        """Execute bash code."""
        proc = await asyncio.create_subprocess_shell(
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout or self._timeout,
            )
            return {
                "stdout": stdout.decode("utf-8", errors="replace")[:self._max_output],
                "stderr": stderr.decode("utf-8", errors="replace")[:self._max_output],
                "exit_code": proc.returncode,
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {
                "stdout": "",
                "stderr": "Execution timed out",
                "exit_code": -1,
            }

    def set_timeout(self, timeout: float) -> None:
        """Set execution timeout."""
        self._timeout = timeout

    def set_max_output(self, max_output: int) -> None:
        """Set max output size."""
        self._max_output = max_output
