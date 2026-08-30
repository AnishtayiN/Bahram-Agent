from __future__ import annotations

import logging
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SERVICE_NAME = "bahram-agent"
CONFIG_DIR = Path.home() / ".config" / "bahram"
UNIT_FILE = Path("/etc/systemd/system/bahram-agent.service")
PLIST_FILE = Path.home() / "Library" / "LaunchAgents" / "com.bahram.agent.plist"


class GatewayService:
    def __init__(self, work_dir: str | None = None) -> None:
        self._platform = platform.system().lower()
        self._work_dir = work_dir or os.getcwd()
        self._python_path = sys.executable

    def install_service(self, system: bool = False) -> dict:
        if self._platform == "linux":
            return self._install_systemd(system)
        elif self._platform == "darwin":
            return self._install_launchd()
        return {"error": f"Unsupported platform: {self._platform}"}

    def uninstall_service(self) -> dict:
        if self._platform == "linux":
            return self._uninstall_systemd()
        elif self._platform == "darwin":
            return self._uninstall_launchd()
        return {"error": f"Unsupported platform: {self._platform}"}

    def start_service(self) -> dict:
        if self._platform == "linux":
            return self._systemctl("start")
        elif self._platform == "darwin":
            return self._launchctl("load")
        return {"error": f"Unsupported platform: {self._platform}"}

    def stop_service(self) -> dict:
        if self._platform == "linux":
            return self._systemctl("stop")
        elif self._platform == "darwin":
            return self._launchctl("unload")
        return {"error": f"Unsupported platform: {self._platform}"}

    def get_status(self) -> dict:
        if self._platform == "linux":
            return self._systemctl("is-active")
        elif self._platform == "darwin":
            return self._launchctl_list()
        return {"status": "unknown", "platform": self._platform}

    def _generate_systemd_unit(self, system: bool) -> str:
        user_section = ""
        exec_start = f"{self._python_path} -m bahram gateway"
        if not system:
            user_section = "User=%s\n" % os.getenv("USER", "bahram")
            target_dir = CONFIG_DIR
        else:
            target_dir = Path("/opt/bahram")

        return f"""[Unit]
Description=Bahram AI Agent Gateway
After=network.target
Wants=network-online.target

[Service]
Type=simple
{user_section}WorkingDirectory={self._work_dir}
ExecStart={exec_start}
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=BAHRAM_CONFIG={target_dir}/config.yaml

[Install]
WantedBy={'default.target' if not system else 'multi-user.target'}
"""

    def _install_systemd(self, system: bool) -> dict:
        try:
            unit_content = self._generate_systemd_unit(system)
            target = UNIT_FILE if system else Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(unit_content)
            logger.info(f"Systemd unit written to {target}")

            if system:
                result = subprocess.run(["systemctl", "daemon-reload"], capture_output=True, text=True)
                if result.returncode != 0:
                    return {"status": "error", "error": result.stderr.strip()}
                result = subprocess.run(["systemctl", "enable", SERVICE_NAME], capture_output=True, text=True)
                if result.returncode != 0:
                    return {"status": "error", "error": result.stderr.strip()}
            else:
                result = subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, text=True)
                if result.returncode != 0:
                    return {"status": "error", "error": result.stderr.strip()}

            return {"status": "installed", "type": "systemd", "unit_path": str(target), "system": system}
        except Exception as e:
            logger.error(f"Failed to install systemd service: {e}")
            return {"status": "error", "error": str(e)}

    def _uninstall_systemd(self) -> dict:
        try:
            self._systemctl("stop")
            user_unit = Path.home() / ".config" / "systemd" / "user" / f"{SERVICE_NAME}.service"
            for path in [UNIT_FILE, user_unit]:
                if path.exists():
                    path.unlink()
                    logger.info(f"Removed unit file: {path}")
            subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
            return {"status": "uninstalled"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _systemctl(self, action: str) -> dict:
        try:
            if action == "is-active":
                for flag in [[], ["--user"]]:
                    result = subprocess.run(
                        ["systemctl"] + flag + [action, SERVICE_NAME],
                        capture_output=True, text=True, timeout=10,
                    )
                    active = result.stdout.strip() == "active"
                    return {"status": "active" if active else "inactive", "action": action}
                return {"status": "unknown", "action": action}

            for flag in [[], ["--user"]]:
                result = subprocess.run(
                    ["systemctl"] + flag + [action, SERVICE_NAME],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    return {"status": "ok", "action": action}
            return {"status": "error", "action": action, "error": "Command failed"}
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "action": action}
        except FileNotFoundError:
            return {"status": "error", "action": action, "error": "systemctl not found"}
        except Exception as e:
            return {"status": "error", "action": action, "error": str(e)}

    def _install_launchd(self) -> dict:
        try:
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.bahram.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>{self._python_path}</string>
        <string>-m</string>
        <string>bahram</string>
        <string>gateway</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{self._work_dir}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>{Path.home()}/.bahram/gateway.log</string>
    <key>StandardErrorPath</key>
    <string>{Path.home()}/.bahram/gateway.error.log</string>
</dict>
</plist>
"""
            PLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
            PLIST_FILE.write_text(plist_content)
            logger.info(f"launchd plist written to {PLIST_FILE}")
            return {"status": "installed", "type": "launchd", "plist_path": str(PLIST_FILE)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _uninstall_launchd(self) -> dict:
        try:
            self._launchctl("unload")
            if PLIST_FILE.exists():
                PLIST_FILE.unlink()
            return {"status": "uninstalled"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _launchctl(self, action: str) -> dict:
        try:
            if action == "list":
                result = subprocess.run(
                    ["launchctl", "list", "com.bahram.agent"],
                    capture_output=True, text=True, timeout=10,
                )
                running = result.returncode == 0
                return {"status": "active" if running else "inactive", "action": action}

            result = subprocess.run(
                ["launchctl", action, str(PLIST_FILE)],
                capture_output=True, text=True, timeout=30,
            )
            return {"status": "ok" if result.returncode == 0 else "error", "action": action}
        except FileNotFoundError:
            return {"status": "error", "action": action, "error": "launchctl not found"}
        except Exception as e:
            return {"status": "error", "action": action, "error": str(e)}
