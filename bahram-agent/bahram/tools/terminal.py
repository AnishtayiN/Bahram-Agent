"""Terminal backends for Bahram Agent."""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TerminalConfig:
    """Terminal backend configuration."""

    backend: str = "local"
    cwd: str = "."
    timeout: int = 180
    docker_image: str = "python:3.11-slim"
    container_cpu: int = 1
    container_memory: int = 5120
    container_disk: int = 51200
    container_persistent: bool = True
    ssh_host: str = ""
    ssh_user: str = ""
    ssh_key: str = ""


class TerminalBackend(ABC):
    """Base terminal backend."""

    @abstractmethod
    async def execute(
        self,
        command: str,
        cwd: str = ".",
        timeout: int = 180,
        background: bool = False,
    ) -> dict[str, Any]:
        """Execute a command."""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up resources."""
        pass


class LocalBackend(TerminalBackend):
    """Local terminal backend."""

    async def execute(
        self,
        command: str,
        cwd: str = ".",
        timeout: int = 180,
        background: bool = False,
    ) -> dict[str, Any]:
        """Execute command locally."""
        try:
            if background:
                process = await asyncio.create_subprocess_shell(
                    command,
                    cwd=cwd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                return {
                    "status": "running",
                    "pid": process.pid,
                    "message": f"Background process started with PID {process.pid}",
                }

            result = await asyncio.wait_for(
                asyncio.create_subprocess_shell(
                    command,
                    cwd=cwd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=timeout,
            )

            stdout, stderr = await result.communicate()

            return {
                "status": "completed",
                "exit_code": result.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }

        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "error": f"Command timed out after {timeout}s",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    async def cleanup(self) -> None:
        """No cleanup needed for local backend."""
        pass


class DockerBackend(TerminalBackend):
    """Docker container backend."""

    def __init__(self, config: TerminalConfig = None) -> None:
        self.config = config or TerminalConfig()
        self._container_id: Optional[str] = None

    async def _ensure_container(self) -> str:
        """Ensure Docker container is running."""
        if self._container_id:
            return self._container_id

        # Start new container
        cmd = [
            "docker", "run", "-d",
            "--rm",
            "--cap-drop", "ALL",
            "--cap-add", "DAC_OVERRIDE",
            "--cap-add", "CHOWN",
            "--cap-add", "FOWNER",
            "--security-opt", "no-new-privileges",
            "--pids-limit", "256",
            "--memory", f"{self.config.container_memory}m",
            "--cpus", str(self.config.container_cpu),
            "--tmpfs", "/tmp:rw,nosuid,size=512m",
            self.config.docker_image,
            "sleep", "infinity",
        ]

        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await result.communicate()
        self._container_id = stdout.decode().strip()

        logger.info(f"Started Docker container: {self._container_id[:12]}")
        return self._container_id

    async def execute(
        self,
        command: str,
        cwd: str = ".",
        timeout: int = 180,
        background: bool = False,
    ) -> dict[str, Any]:
        """Execute command in Docker."""
        container_id = await self._ensure_container()

        docker_cmd = [
            "docker", "exec",
            container_id,
            "bash", "-c", command,
        ]

        try:
            if background:
                process = await asyncio.create_subprocess_exec(
                    *docker_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                return {
                    "status": "running",
                    "pid": process.pid,
                    "message": f"Background process started in container",
                }

            result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *docker_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=timeout,
            )

            stdout, stderr = await result.communicate()

            return {
                "status": "completed",
                "exit_code": result.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }

        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "error": f"Command timed out after {timeout}s",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    async def cleanup(self) -> None:
        """Stop Docker container."""
        if self._container_id:
            try:
                await asyncio.create_subprocess_exec(
                    "docker", "stop", self._container_id,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                logger.info(f"Stopped Docker container: {self._container_id[:12]}")
            except Exception as e:
                logger.error(f"Failed to stop container: {e}")
            self._container_id = None


class SSHBackend(TerminalBackend):
    """SSH remote backend."""

    def __init__(self, config: TerminalConfig = None) -> None:
        self.config = config or TerminalConfig()

    async def execute(
        self,
        command: str,
        cwd: str = ".",
        timeout: int = 180,
        background: bool = False,
    ) -> dict[str, Any]:
        """Execute command via SSH."""
        ssh_cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
        ]

        if self.config.ssh_key:
            ssh_cmd.extend(["-i", self.config.ssh_key])

        ssh_cmd.append(f"{self.config.ssh_user}@{self.config.ssh_host}")
        ssh_cmd.append(f"cd {cwd} && {command}")

        try:
            result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *ssh_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=timeout,
            )

            stdout, stderr = await result.communicate()

            return {
                "status": "completed",
                "exit_code": result.returncode,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
            }

        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "error": f"SSH command timed out after {timeout}s",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    async def cleanup(self) -> None:
        """No cleanup needed for SSH backend."""
        pass


class TerminalManager:
    """Manage terminal backends."""

    def __init__(self, config: TerminalConfig = None) -> None:
        self.config = config or TerminalConfig()
        self._backends: dict[str, TerminalBackend] = {
            "local": LocalBackend(),
            "docker": DockerBackend(self.config),
            "ssh": SSHBackend(self.config),
        }

    def get_backend(self) -> TerminalBackend:
        """Get the active backend."""
        backend = self._backends.get(self.config.backend)
        if not backend:
            logger.warning(f"Unknown backend {self.config.backend}, using local")
            backend = self._backends["local"]
        return backend

    async def execute(
        self,
        command: str,
        cwd: str = None,
        timeout: int = None,
        background: bool = False,
    ) -> dict[str, Any]:
        """Execute command using configured backend."""
        backend = self.get_backend()
        return await backend.execute(
            command,
            cwd=cwd or self.config.cwd,
            timeout=timeout or self.config.timeout,
            background=background,
        )

    async def cleanup(self) -> None:
        """Clean up all backends."""
        for backend in self._backends.values():
            await backend.cleanup()
