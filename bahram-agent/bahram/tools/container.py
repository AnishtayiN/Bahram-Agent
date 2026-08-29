"""Container resources and security for Bahram Agent."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ContainerResources:
    """Container resource limits."""

    cpu: int = 1
    memory_mb: int = 5120
    disk_mb: int = 51200
    pids_limit: int = 256
    persistent: bool = True
    read_only_root: bool = True


@dataclass
class ContainerSecurity:
    """Container security configuration."""

    drop_all_caps: bool = True
    add_caps: list[str] = field(default_factory=lambda: ["DAC_OVERRIDE", "CHOWN", "FOWNER"])
    no_new_privileges: bool = True
    security_opt: list[str] = field(default_factory=lambda: ["no-new-privileges"])


class ContainerManager:
    """Manage container resources and security."""

    def __init__(
        self,
        resources: ContainerResources = None,
        security: ContainerSecurity = None,
    ) -> None:
        self.resources = resources or ContainerResources()
        self.security = security or ContainerSecurity()

    def get_docker_args(self) -> list[str]:
        """Get Docker arguments for resources and security."""
        args = []

        # Resources
        args.extend(["--memory", f"{self.resources.memory_mb}m"])
        args.extend(["--cpus", str(self.resources.cpu)])
        args.extend(["--pids-limit", str(self.resources.pids_limit)])

        # Security
        if self.security.drop_all_caps:
            args.extend(["--cap-drop", "ALL"])
            for cap in self.security.add_caps:
                args.extend(["--cap-add", cap])

        if self.security.no_new_privileges:
            args.extend(["--security-opt", "no-new-privileges"])

        if self.resources.read_only_root:
            args.append("--read-only")

        # Tmpfs
        args.extend(["--tmpfs", "/tmp:rw,nosuid,size=512m"])
        args.extend(["--tmpfs", "/var/tmp:rw,noexec,nosuid,size=256m"])

        return args

    def get_env_passthrough(self) -> list[str]:
        """Get environment variables safe for container passthrough."""
        safe_vars = [
            "PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM", "SHELL", "TMPDIR",
        ]
        return safe_vars

    def get_credential_files(self) -> list[str]:
        """Get credential files to mount in container."""
        return [
            "google_token.json",
            "google_client_secret.json",
        ]
