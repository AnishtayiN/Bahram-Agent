from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


class LazyLoader:
    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._failed: set[str] = set()

    def __getattr__(self, name: str) -> Any:
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

    def load(self, module_name: str) -> Any | None:
        try:
            return getattr(self, module_name)
        except ImportError:
            return None

    def is_available(self, module_name: str) -> bool:
        try:
            self.load(module_name)
            return True
        except ImportError:
            return False

    def preload(self, module_names: list[str]) -> dict[str, bool]:
        results = {}
        for name in module_names:
            results[name] = self.is_available(name)
        return results


_lazy = LazyLoader()


def lazy_import(module_name: str) -> Any | None:
    return _lazy.load(module_name)


def require_optional(module_name: str) -> Any:
    try:
        return getattr(_lazy, module_name)
    except ImportError as e:
        raise ImportError(
            f"This feature requires '{module_name}'. Install it with: pip install {module_name}"
        ) from e


def get_httpx():
    return require_optional("httpx")


def get_pydantic():
    return require_optional("pydantic")


def get_yaml():
    return require_optional("yaml")


def get_rich():
    return require_optional("rich")


def get_typer():
    return require_optional("typer")
