"""Lazy dependency installation for Bahram Agent."""

from __future__ import annotations

import logging
import subprocess
import sys
from typing import Any

logger = logging.getLogger(__name__)

# Lazy dependency map
LAZY_DEPS = {
    "voice.openai": ["openai"],
    "voice.whisper": ["openai"],
    "image.openai": ["openai", "httpx"],
    "image.stability": ["httpx"],
    "image.fal": ["httpx"],
    "browser.playwright": ["playwright"],
    "documents.pdf": ["PyPDF2"],
    "documents.docx": ["python-docx"],
    "documents.xlsx": ["openai"],
    "documents.pptx": ["python-pptx"],
    "documents.html": ["beautifulsoup4"],
    "memory.honcho": ["honcho-sdk"],
    "memory.mem0": ["mem0ai"],
    "tts.openai": ["openai"],
    "mcp.client": ["mcp"],
}


class LazyDependencyManager:
    """Manage lazy installation of optional dependencies."""

    def __init__(self) -> None:
        self._installed: set[str] = set()
        self._allow_installs = True

    def ensure(self, feature: str) -> bool:
        """Ensure dependencies for a feature are installed.

        Returns:
            True if dependencies are available
        """
        deps = LAZY_DEPS.get(feature, [])
        if not deps:
            return True

        for dep in deps:
            if dep not in self._installed:
                if not self._install_dep(dep):
                    return False
                self._installed.add(dep)

        return True

    def _install_dep(self, dep: str) -> bool:
        """Install a single dependency."""
        if not self._allow_installs:
            logger.warning(f"Lazy installs disabled, missing: {dep}")
            return False

        try:
            logger.info(f"Lazily installing: {dep}")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", dep],
                capture_output=True,
                timeout=60,
            )
            if result.returncode == 0:
                logger.info(f"Successfully installed: {dep}")
                return True
            else:
                logger.error(f"Failed to install {dep}: {result.stderr.decode()}")
                return False
        except Exception as e:
            logger.error(f"Failed to install {dep}: {e}")
            return False

    def set_allow_installs(self, allow: bool) -> None:
        """Enable/disable lazy installs."""
        self._allow_installs = allow

    def is_available(self, feature: str) -> bool:
        """Check if a feature's deps are available."""
        deps = LAZY_DEPS.get(feature, [])
        return all(self._check_dep(d) for d in deps)

    def _check_dep(self, dep: str) -> bool:
        """Check if a dependency is installed."""
        try:
            __import__(dep.replace("-", "_").split("[")[0])
            return True
        except ImportError:
            return False
