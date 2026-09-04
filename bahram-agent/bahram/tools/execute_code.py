from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any

from bahram.tools.base import BaseTool

logger = logging.getLogger(__name__)

class ExecuteCodeTool(BaseTool):
    @property
    def name(self) -> str:
        return "execute_code"

    @property
    def description(self) -> str:
        return "Execute code in a sandboxed subprocess. Supports python and bash."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The code to execute",
                },
                "language": {
                    "type": "string",
                    "enum": ["python", "bash"],
                    "description": "Programming language (default: python)",
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (default: 30)",
                },
            },
            "required": ["code"],
        }

    def __init__(self, config: Any = None) -> None:
        super().__init__(config)
        self._timeout: float = float(getattr(config, "code_timeout", 30) or 30)
        self._max_output: int = int(getattr(config, "code_max_output", 10000) or 10000)

    async def execute(self, **kwargs: Any) -> str:
        code = kwargs.get("code", "")
        language = kwargs.get("language", "python")
        timeout = kwargs.get("timeout", self._timeout)

        if not code:
            return "Error: No code provided"

        if language == "python":
            result = await self._execute_python(code, timeout)
        elif language == "bash":
            result = await self._execute_bash(code, timeout)
        else:
            return f"Error: Unsupported language: {language}"

        parts = []
        if result.get("stdout"):
            parts.append(f"STDOUT:\n{result['stdout']}")
        if result.get("stderr"):
            parts.append(f"STDERR:\n{result['stderr']}")
        parts.append(f"\nExit code: {result.get('exit_code', -1)}")
        return "\n".join(parts)

    async def _execute_python(self, code: str, timeout: float = None) -> dict[str, Any]:
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
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout or self._timeout)
                return {
                    "stdout": stdout.decode("utf-8", errors="replace")[:self._max_output],
                    "stderr": stderr.decode("utf-8", errors="replace")[:self._max_output],
                    "exit_code": proc.returncode,
                }
            except asyncio.TimeoutError:
                proc.kill()
                return {"stdout": "", "stderr": "Execution timed out", "exit_code": -1}
        finally:
            Path(temp_path).unlink(missing_ok=True)

    async def _execute_bash(self, code: str, timeout: float = None) -> dict[str, Any]:
        proc = await asyncio.create_subprocess_shell(
            code, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout or self._timeout)
            return {
                "stdout": stdout.decode("utf-8", errors="replace")[:self._max_output],
                "stderr": stderr.decode("utf-8", errors="replace")[:self._max_output],
                "exit_code": proc.returncode,
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {"stdout": "", "stderr": "Execution timed out", "exit_code": -1}
