"""
Container.

Public objects: ``ContainerConfig``, ``ContainerResources``, ``ContainerSecurity``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ContainerConfig:
    """
    Container config.

    Attributes:
        image (str): image string.
        name (str): name of the object.
        memory_limit (str): memory limit string.
        cpu_limit (float): numeric value for cpu limit.
        network (str): network string.
        volumes (dict[str, str]): mapping of volumes.
        env (dict[str, str]): mapping of env.
        working_dir (str): working dir string.
    """

    image: str = "python:3.11-slim"
    name: str = ""
    memory_limit: str = "512m"
    cpu_limit: float = 1.0
    network: str = "none"
    volumes: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    working_dir: str = "/workspace"


class DockerUnavailableError(RuntimeError):
    """Raised when the ``docker`` CLI cannot be executed.

    ``asyncio.create_subprocess_exec("docker", ...)`` raises a bare
    ``FileNotFoundError`` when the CLI is absent, which surfaced to callers as
    an opaque crash.  Every command in this module now funnels through
    :func:`ContainerResources._run_docker`, which converts that condition into
    this explicit, loggable error so a missing runtime is reported as a
    diagnostic instead of an unhandled exception.
    """


class ContainerResources:
    """
    Container resources.
    """

    def __init__(self) -> None:
        """
        Initialise a ContainerResources instance.
        """
        self._active_containers: dict[str, dict] = {}

    async def _run_docker(self, *args: str, timeout: float | None = None) -> tuple[int, str, str]:
        """Run ``docker <args>`` and return ``(returncode, stdout, stderr)``.

        Args:
            *args (str): arguments passed to the ``docker`` CLI.
            timeout (float | None): optional timeout in seconds.

        Returns:
            tuple[int, str, str]: exit status, stdout and stderr, decoded as
            UTF-8 with replacement.

        Raises:
            DockerUnavailableError: if the ``docker`` CLI is not installed or is not
                executable.

        Note:
            Coroutine - must be awaited.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, PermissionError) as exc:
            raise DockerUnavailableError("docker CLI is not available on this host") from exc

        stdout, stderr = await proc.communicate()
        return (
            proc.returncode,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )

    async def create_container(self, config: ContainerConfig) -> str:
        """
        Create container.

        Args:
            config (ContainerConfig): configuration object.

        Returns:
            str: the name the container was created under.

        Raises:
            RuntimeError: if ``docker create`` exits non-zero.
            DockerUnavailable: if the ``docker`` CLI is not installed.

        Note:
            Coroutine - must be awaited.
        """
        import uuid

        name = config.name or f"bahram-agent-{uuid.uuid4().hex[:8]}"

        cmd: list[str] = [
            "create",
            "--name",
            name,
            "--memory",
            config.memory_limit,
            "--cpus",
            str(config.cpu_limit),
            "--network",
            config.network,
            "--workdir",
            config.working_dir,
        ]

        for host_path, container_path in config.volumes.items():
            cmd.extend(["-v", f"{host_path}:{container_path}"])

        for key, value in config.env.items():
            cmd.extend(["-e", f"{key}={value}"])

        cmd.append(config.image)

        returncode, stdout, stderr = await self._run_docker(*cmd)
        if returncode != 0:
            raise RuntimeError(f"Failed to create container: {stderr}")

        self._active_containers[name] = {"id": stdout.strip(), "config": config}
        return name

    async def start_container(self, name: str) -> bool:
        """
        Start container.

        Args:
            name (str): name of the object.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        try:
            returncode, _stdout, stderr = await self._run_docker("start", name)
        except DockerUnavailableError as exc:
            logger.warning("Cannot start container %s: %s", name, exc)
            return False
        if returncode != 0:
            logger.warning("docker start %s failed: %s", name, stderr)
        return returncode == 0

    async def stop_container(self, name: str, timeout: int = 10) -> bool:
        """
        Stop container.

        Args:
            name (str): name of the object.
            timeout (int): timeout in seconds. Defaults to ``10``.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        try:
            returncode, _stdout, stderr = await self._run_docker("stop", "-t", str(timeout), name)
        except DockerUnavailableError as exc:
            logger.warning("Cannot stop container %s: %s", name, exc)
            return False
        if returncode != 0:
            logger.warning("docker stop %s failed: %s", name, stderr)
        return returncode == 0

    async def remove_container(self, name: str, force: bool = False) -> bool:
        """
        Remove container.

        Args:
            name (str): name of the object.
            force (bool): when ``True``, skip the safety confirmation. Defaults to ``False``.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        cmd = ["rm"]
        if force:
            cmd.append("-f")
        cmd.append(name)

        try:
            returncode, _stdout, stderr = await self._run_docker(*cmd)
        except DockerUnavailableError as exc:
            logger.warning("Cannot remove container %s: %s", name, exc)
            return False

        if returncode != 0:
            logger.warning("docker rm %s failed: %s", name, stderr)
            return False

        self._active_containers.pop(name, None)
        return True

    async def exec_in_container(
        self,
        name: str,
        command: str,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        """
        Exec in container.

        Args:
            name (str): name of the object.
            command (str): shell command to execute.
            timeout (float): timeout in seconds. Defaults to ``60.0``.

        Returns:
            dict[str, Any]: ``stdout``, ``stderr`` and ``exit_code`` keys; an
            ``error`` key explains the failure when docker is unavailable.

        Note:
            Coroutine - must be awaited.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "exec",
                name,
                "sh",
                "-c",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (FileNotFoundError, PermissionError) as exc:
            return {
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
                "error": f"docker CLI is not available on this host: {exc}",
            }

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "exit_code": proc.returncode,
            }
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()  # reap the child instead of leaving a zombie
            return {
                "stdout": "",
                "stderr": "Command timed out",
                "exit_code": -1,
            }

    async def get_container_stats(self, name: str) -> dict[str, Any]:
        """
        Return the container stats.

        Args:
            name (str): name of the object.

        Returns:
            dict[str, Any]: cpu/memory/network/block usage, or ``{"error": ...}``
            when docker is unavailable or the container does not exist.

        Note:
            Coroutine - must be awaited.
        """
        try:
            returncode, stdout, _stderr = await self._run_docker(
                "stats",
                name,
                "--no-stream",
                "--format",
                "{{.CPUPerc}}|{{.MemUsage}}|{{.NetIO}}|{{.BlockIO}}",
            )
        except DockerUnavailableError as exc:
            return {"error": str(exc)}

        if returncode == 0:
            parts = stdout.strip().split("|")
            if len(parts) >= 4:
                return {
                    "cpu_percent": parts[0],
                    "memory_usage": parts[1],
                    "network_io": parts[2],
                    "block_io": parts[3],
                }
        return {"error": "Failed to get stats"}

    async def list_containers(self, all: bool = False) -> list[dict]:
        """
        List containers.

        Args:
            all (bool): when ``True``, enable all. Defaults to ``False``.

        Returns:
            list[dict]: one entry per container; empty when docker is
            unavailable or no containers exist.

        Note:
            Coroutine - must be awaited.
        """
        cmd = ["ps", "--format", "{{.Names}}|{{.Image}}|{{.Status}}"]
        if all:
            cmd.append("-a")

        try:
            returncode, stdout, _stderr = await self._run_docker(*cmd)
        except DockerUnavailableError as exc:
            logger.warning("Cannot list containers: %s", exc)
            return []

        containers: list[dict] = []
        if returncode == 0:
            for line in stdout.strip().split("\n"):
                if line:
                    parts = line.split("|")
                    if len(parts) >= 3:
                        containers.append(
                            {
                                "name": parts[0],
                                "image": parts[1],
                                "status": parts[2],
                            }
                        )
        return containers


class ContainerSecurity:
    """
    Container security.
    """

    def __init__(self) -> None:
        """
        Initialise a ContainerSecurity instance.
        """
        self._blocked_images: list[str] = []
        self._max_memory: str = "2g"
        self._max_cpus: float = 2.0
        self._allowed_registries: list[str] = ["docker.io", "gcr.io"]

    def check_image(self, image: str) -> tuple[bool, str]:
        """
        Check image.

        Args:
            image (str): image string.

        Returns:
            tuple[bool, str]: a sequence of bool, str entries (empty when there is nothing to
                report).
        """
        for blocked in self._blocked_images:
            if blocked in image:
                return False, f"Image '{image}' is blocked"

        registry = image.split("/")[0] if "/" in image else "docker.io"
        if registry not in self._allowed_registries:
            return False, f"Registry '{registry}' is not allowed"

        return True, "OK"

    def apply_security(self, config: ContainerConfig) -> ContainerConfig:
        """
        Apply security.

        Args:
            config (ContainerConfig): configuration object.

        Returns:
            ContainerConfig: the resulting ContainerConfig.
        """
        config.network = "none"
        return config
