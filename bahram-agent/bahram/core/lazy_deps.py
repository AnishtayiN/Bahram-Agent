"""Lazy dependency loader for Bahram Agent."""

from __future__ import annotations

import importlib
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LazyLoader:
    """Lazy load dependencies to improve startup time."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._failed: set[str] = set()

    def __getattr__(self, name: str) -> Any:
        """Lazy load a module attribute."""
        if name in self._cache:
            return self._cache[name]

        if name in self._failed:
            raise ImportError(f"Module '{name}' failed to load")

        try:
            module = importlib.import_module(name)
            self._cache[name] = module
            return module
        except ImportError as e:
            self._failed.add(name)
            raise ImportError(f"Optional dependency '{name}' not installed: {e}")

    def load(self, module_name: str) -> Optional[Any]:
        """Load a module."""
        try:
            return getattr(self, module_name)
        except ImportError:
            return None

    def is_available(self, module_name: str) -> bool:
        """Check if a module is available."""
        try:
            self.load(module_name)
            return True
        except ImportError:
            return False

    def preload(self, module_names: list[str]) -> dict[str, bool]:
        """Preload multiple modules."""
        results = {}
        for name in module_names:
            results[name] = self.is_available(name)
        return results


# Global lazy loader
_lazy = LazyLoader()


def lazy_import(module_name: str) -> Optional[Any]:
    """Lazy import a module."""
    return _lazy.load(module_name)


def require_optional(module_name: str) -> Any:
    """Require an optional module, raise clear error if missing."""
    try:
        return getattr(_lazy, module_name)
    except ImportError as e:
        raise ImportError(
            f"This feature requires '{module_name}'. "
            f"Install it with: pip install {module_name}"
        ) from e


# Common lazy imports
def get_httpx():
    """Get httpx client."""
    return require_optional("httpx")


def get_pydantic():
    """Get pydantic."""
    return require_optional("pydantic")


def get_yaml():
    """Get yaml."""
    return require_optional("yaml")


def get_rich():
    """Get rich."""
    return require_optional("rich")


def get_typer():
    """Get typer."""
    return require_optional("typer")
