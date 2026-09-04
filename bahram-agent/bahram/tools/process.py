from __future__ import annotations

import asyncio
import logging
import os
import signal
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class ProcessInfo:

    pid: int
    name: str
    command: str
    status: str = "running"
    start_time: float = 0.0
    cpu_percent: float = 0.0
    memory_percent: float = 0.0

class ProcessManager:

    def __init__(self) -> None:
        self._processes: dict[int, ProcessInfo] = {}
        self._max_processes: int = 10

    async def start(
        self,
        name: str,
        command: str,
        cwd: str = None,
        env: dict[str, str] = None,
    ) -> ProcessInfo:
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
        return self._processes.get(pid)

    def list_processes(self) -> list[dict]:
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
        to_remove = [
            pid for pid, info in self._processes.items()
            if info.status in ("completed", "failed")
        ]
        for pid in to_remove:
            del self._processes[pid]
        return len(to_remove)
