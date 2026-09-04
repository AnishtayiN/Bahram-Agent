from __future__ import annotations

import logging
import platform
from pathlib import Path

logger = logging.getLogger(__name__)

class InstallationManager:

    def __init__(self) -> None:
        self._platform = platform.system().lower()

    def get_install_script(self) -> str:
        if self._platform == "linux" or self._platform == "darwin":
            return self._get_bash_script()
        elif self._platform == "windows":
            return self._get_powershell_script()
        return "# Unsupported platform"

    def _get_bash_script(self) -> str:
        return ""

    def _get_powershell_script(self) -> str:
        return ""

    def get_setup_wizard(self) -> str:
        return ""
