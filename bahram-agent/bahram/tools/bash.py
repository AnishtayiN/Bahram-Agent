from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from bahram.tools.base import BaseTool

logger = logging.getLogger(__name__)

_tirith_scanner = None
_supply_chain = None

def _get_tirith():
    global _tirith_scanner
    if _tirith_scanner is None:
        try:
            from bahram.security.tirith import TirithScanner
            _tirith_scanner = TirithScanner()
        except Exception:
            pass
    return _tirith_scanner

def _get_supply_chain():
    global _supply_chain
    if _supply_chain is None:
        try:
            from bahram.security.supply_chain import SupplyChainGuard
            _supply_chain = SupplyChainGuard()
        except Exception:
            pass
    return _supply_chain

class BashTool(BaseTool):
    def __init__(self, config: Any = None) -> None:
        self.config = config
        self.timeout = getattr(config, "bash_timeout", 120) if config else 120

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return "Execute a bash command and return its output."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute",
                },
                "workdir": {
                    "type": "string",
                    "description": "Working directory (optional)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (optional)",
                },
            },
            "required": ["command"],
        }

    async def execute(self, **kwargs: Any) -> str:
        command = kwargs.get("command", "")
        workdir = kwargs.get("workdir", os.getcwd())
        timeout = kwargs.get("timeout", self.timeout)

        if not command:
            return "Error: No command provided"

        tirith = _get_tirith()
        if tirith:
            result = tirith.scan_command(command)
            if result is not None and hasattr(result, "safe") and not result.safe:
                violations = list(result.blocked or []) + list(result.issues or [])
                return f"Error: Security violations: {'; '.join(violations)}"

        supply = _get_supply_chain()
        if supply and hasattr(supply, "validate_command"):
            safe, msg = supply.validate_command(command)
            if not safe:
                return f"Error: Supply chain: {msg}"

        logger.info(f"Executing bash command: {command}")

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                return f"Error: Command timed out after {timeout} seconds"

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            output = []
            if stdout_str:
                output.append(f"STDOUT:\n{stdout_str}")
            if stderr_str:
                output.append(f"STDERR:\n{stderr_str}")

            exit_code = process.returncode
            output.append(f"\nExit code: {exit_code}")

            if exit_code != 0:
                logger.warning(f"Command failed with exit code {exit_code}")

            return "\n".join(output)

        except Exception as e:
            error_msg = f"Error executing command: {e}"
            logger.error(error_msg)
            return error_msg
