"""Background process management for Bahram Agent."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """Information about a background process."""

    session_id: str
    pid: int
    command: str
    status: str = "running"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    process: Any = None


class ProcessManager:
    """Manage background processes."""

    def __init__(self) -> None:
        self._processes: dict[str, ProcessInfo] = {}
        self._counter = 0

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        self._counter += 1
        return f"proc_{self._counter:06d}"

    async def start_process(
        self,
        command: str,
        cwd: str = ".",
    ) -> ProcessInfo:
        """Start a background process."""
        session_id = self._generate_session_id()

        process = await asyncio.create_subprocess_shell(
            command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        info = ProcessInfo(
            session_id=session_id,
            pid=process.pid,
            command=command,
            process=process,
        )

        self._processes[session_id] = info
        logger.info(f"Started background process {session_id}: PID {process.pid}")

        return info

    async def poll_process(self, session_id: str) -> Optional[dict]:
        """Poll process status."""
        info = self._processes.get(session_id)
        if not info:
            return None

        if info.process:
            returncode = info.process.returncode
            if returncode is not None:
                info.status = "completed"
                info.exit_code = returncode

                stdout, stderr = await info.process.communicate()
                info.stdout = stdout.decode("utf-8", errors="replace")
                info.stderr = stderr.decode("utf-8", errors="replace")

        return {
            "session_id": info.session_id,
            "pid": info.pid,
            "status": info.status,
            "exit_code": info.exit_code,
        }

    async def wait_process(self, session_id: str, timeout: float = None) -> Optional[dict]:
        """Wait for process to complete."""
        info = self._processes.get(session_id)
        if not info or not info.process:
            return None

        try:
            await asyncio.wait_for(
                info.process.wait(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return {
                "session_id": session_id,
                "status": "timeout",
            }

        return await self.poll_process(session_id)

    async def get_log(self, session_id: str) -> Optional[str]:
        """Get process output."""
        info = self._processes.get(session_id)
        if not info:
            return None

        if info.status == "completed":
            return f"STDOUT:\n{info.stdout}\n\nSTDERR:\n{info.stderr}"

        return f"Process {session_id} is still running (PID: {info.pid})"

    async def kill_process(self, session_id: str) -> bool:
        """Kill a process."""
        info = self._processes.get(session_id)
        if not info or not info.process:
            return False

        info.process.terminate()
        try:
            await asyncio.wait_for(info.process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            info.process.kill()

        info.status = "killed"
        logger.info(f"Killed process {session_id}")
        return True

    async def write_stdin(self, session_id: str, data: str) -> bool:
        """Write to process stdin."""
        info = self._processes.get(session_id)
        if not info or not info.process or not info.process.stdin:
            return False

        info.process.stdin.write(data.encode())
        await info.process.stdin.drain()
        return True

    def list_processes(self) -> list[dict]:
        """List all processes."""
        return [
            {
                "session_id": info.session_id,
                "pid": info.pid,
                "command": info.command[:100],
                "status": info.status,
                "created_at": info.created_at,
            }
            for info in self._processes.values()
        ]

    async def cleanup(self) -> None:
        """Kill all processes."""
        for session_id in list(self._processes.keys()):
            await self.kill_process(session_id)
