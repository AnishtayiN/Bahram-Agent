"""
Bash.

Public objects: ``BashTool``.
"""

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
        except Exception as exc:  # pragma: no cover - defensive
            # Fail loudly: a missing guard must never be invisible.
            logger.warning(
                "Security component could not be initialised (%s): %s",
                "command scanner",
                exc,
            )
    return _tirith_scanner


def _get_supply_chain():
    global _supply_chain
    if _supply_chain is None:
        try:
            from bahram.security.supply_chain import SupplyChainGuard

            _supply_chain = SupplyChainGuard()
        except Exception as exc:  # pragma: no cover - defensive
            # Fail loudly: a missing guard must never be invisible.
            logger.warning(
                "Security component could not be initialised (%s): %s",
                "supply-chain guard",
                exc,
            )
    return _supply_chain


class BashTool(BaseTool):
    """
    Bash tool.
    """

    def __init__(self, config: Any = None) -> None:
        """
        Initialise a BashTool instance.

        Args:
            config (Any): configuration object. Defaults to ``None``.
        """
        self.config = config
        self.timeout = getattr(config, "bash_timeout", 120) if config else 120

    @property
    def name(self) -> str:
        """
        Return the registry name of the BashTool object.

        Returns the constant string ``'bash'``.

        Returns:
            str: the rendered string.
        """
        return "bash"

    @property
    def description(self) -> str:
        """
        Return the human readable description shown to the model.

        Returns the constant string ``'Execute a bash command and return its output.'``.

        Returns:
            str: the rendered string.
        """
        return "Execute a bash command and return its output."

    @property
    def parameters(self) -> dict[str, Any]:
        """
        Return the JSON schema describing this tool's arguments.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
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
        """
        Execute the tool and return its textual result.

        Args:
            **kwargs (Any): keyword arguments forwarded to the implementation.

        Returns:
            str: the rendered string.

        Note:
            Coroutine - must be awaited.
        """
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
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                await process.wait()  # reap the child instead of leaving a zombie
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
