"""
Process.

Public objects: ``ProcessInfo``, ``ProcessManager``.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """
    Process info.

    Attributes:
        pid (int): numeric value for pid.
        name (str): name of the object.
        command (str): shell command to execute.
        status (str): status string.
        start_time (float): numeric value for start time.
        cpu_percent (float): numeric value for cpu percent.
        memory_percent (float): numeric value for memory percent.
    """

    pid: int
    name: str
    command: str
    status: str = "running"
    start_time: float = 0.0
    cpu_percent: float = 0.0
    memory_percent: float = 0.0


class ProcessManager:
    """
    Process manager.
    """

    def __init__(self) -> None:
        """
        Initialise a ProcessManager instance.
        """
        self._processes: dict[int, ProcessInfo] = {}
        self._max_processes: int = 10

    async def start(
        self,
        name: str,
        command: str,
        cwd: str = None,
        env: dict[str, str] = None,
    ) -> ProcessInfo:
        """
        Start the component and acquire any resources it needs.

        Args:
            name (str): name of the object.
            command (str): shell command to execute.
            cwd (str): cwd string. Defaults to ``None``.
            env (dict[str, str]): mapping of env. Defaults to ``None``.

        Returns:
            ProcessInfo: the resulting ProcessInfo.

        Note:
            Coroutine - must be awaited.
        """
        import time

        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )

        info = ProcessInfo(
            pid=proc.pid,
            name=name,
            command=command,
            status="running",
            start_time=time.time(),
        )
        self._processes[proc.pid] = info

        asyncio.create_task(self._monitor(proc, info))

        return info

    async def _monitor(self, proc: asyncio.subprocess.Process, info: ProcessInfo) -> None:
        try:
            await proc.wait()
            info.status = "completed" if proc.returncode == 0 else "failed"
        except Exception as e:
            info.status = "failed"
            logger.warning(f"Process monitoring failed: {e}")

    async def stop(self, pid: int, force: bool = False) -> bool:
        """
        Stop the component and release any resources it holds.

        Args:
            pid (int): numeric value for pid.
            force (bool): when ``True``, skip the safety confirmation. Defaults to ``False``.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        try:
            if force:
                os.kill(pid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGTERM)
            return True
        except ProcessLookupError:
            return False
        except Exception as e:
            logger.warning(f"Failed to stop process: {e}")
            return False

    async def get_info(self, pid: int) -> ProcessInfo | None:
        """
        Return the info.

        Args:
            pid (int): numeric value for pid.

        Returns:
            ProcessInfo | None: the resulting object, or ``None`` when it is not available.

        Note:
            Coroutine - must be awaited.
        """
        return self._processes.get(pid)

    def list_processes(self) -> list[dict]:
        """
        List processes.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        return [
            {
                "pid": p.pid,
                "name": p.name,
                "status": p.status,
                "command": p.command[:100],
            }
            for p in self._processes.values()
            if p.status == "running"
        ]

    async def cleanup(self) -> int:
        """
        Cleanup.

        Returns:
            int: the computed numeric value.

        Note:
            Coroutine - must be awaited.
        """
        to_remove = [
            pid for pid, info in self._processes.items() if info.status in ("completed", "failed")
        ]
        for pid in to_remove:
            del self._processes[pid]
        return len(to_remove)
