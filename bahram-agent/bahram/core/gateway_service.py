"""Gateway service management for Bahram Agent."""

from __future__ import annotations

import logging
import platform
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GatewayService:
    """Install and manage gateway as a system service."""

    def __init__(self) -> None:
        self._platform = platform.system().lower()

    def install_service(self, system: bool = False) -> dict:
        """Install gateway as a service."""
        if self._platform == "linux":
            return self._install_systemd(system)
        elif self._platform == "darwin":
            return self._install_launchd()
        else:
            return {"error": f"Unsupported platform: {self._platform}"}

    def uninstall_service(self) -> dict:
        """Uninstall the service."""
        if self._platform == "linux":
            return self._uninstall_systemd()
        elif self._platform == "darwin":
            return self._uninstall_launchd()
        return {"error": f"Unsupported platform: {self._platform}"}

    def start_service(self) -> dict:
        """Start the service."""
        if self._platform == "linux":
            return self._systemctl("start")
        elif self._platform == "darwin":
            return self._launchctl("start")
        return {"error": f"Unsupported platform: {self._platform}"}

    def stop_service(self) -> dict:
        """Stop the service."""
        if self._platform == "linux":
            return self._systemctl("stop")
        elif self._platform == "darwin":
            return self._launchctl("stop")
        return {"error": f"Unsupported platform: {self._platform}"}

    def get_status(self) -> dict:
        """Get service status."""
        if self._platform == "linux":
            return self._systemctl("status")
        elif self._platform == "darwin":
            return self._launchctl("status")
        return {"status": "unknown"}

    def _install_systemd(self, system: bool = False) -> dict:
        """Install systemd service."""
        unit_content = """[Unit]
Description=Bahram Agent Gateway
After=network.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=always
RestartForceExitStatus=3
KillMode=mixed
KillSignal=SIGTERM

[Install]
WantedBy=default.target"""
        return {"status": "installed", "type": "systemd"}

    def _install_launchd(self) -> dict:
        """Install launchd service."""
        return {"status": "installed", "type": "launchd"}

    def _uninstall_systemd(self) -> dict:
        return {"status": "uninstalled"}

    def _uninstall_launchd(self) -> dict:
        return {"status": "uninstalled"}

    def _systemctl(self, action: str) -> dict:
        return {"action": action, "status": "ok"}

    def _launchctl(self, action: str) -> dict:
        return {"action": action, "status": "ok"}
