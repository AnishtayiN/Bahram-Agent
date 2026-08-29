"""Execute code tool for Bahram Agent."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CodeExecutor:
    """Execute Python code in a sandboxed environment."""

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    async def execute(
        self,
        code: str,
        language: str = "python",
    ) -> dict[str, Any]:
        """Execute code and return output.

        Returns:
            Dict with 'output' and 'error' keys.
        """
        if language == "python":
            return await self._execute_python(code)
        elif language == "bash":
            return await self._execute_bash(code)
        else:
            return {"error": f"Unsupported language: {language}"}

    async def _execute_python(self, code: str) -> dict[str, Any]:
        """Execute Python code."""
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write(code)
            temp_path = f.name

        try:
            result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "python3", temp_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=self.timeout,
            )

            stdout, stderr = await result.communicate()

            return {
                "output": stdout.decode("utf-8", errors="replace"),
                "error": stderr.decode("utf-8", errors="replace"),
                "exit_code": result.returncode,
            }

        except asyncio.TimeoutError:
            return {"error": f"Execution timed out after {self.timeout}s"}
        except Exception as e:
            return {"error": str(e)}
        finally:
            Path(temp_path).unlink(missing_ok=True)

    async def _execute_bash(self, code: str) -> dict[str, Any]:
        """Execute bash code."""
        try:
            result = await asyncio.wait_for(
                asyncio.create_subprocess_shell(
                    code,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=self.timeout,
            )

            stdout, stderr = await result.communicate()

            return {
                "output": stdout.decode("utf-8", errors="replace"),
                "error": stderr.decode("utf-8", errors="replace"),
                "exit_code": result.returncode,
            }

        except asyncio.TimeoutError:
            return {"error": f"Execution timed out after {self.timeout}s"}
        except Exception as e:
            return {"error": str(e)}
