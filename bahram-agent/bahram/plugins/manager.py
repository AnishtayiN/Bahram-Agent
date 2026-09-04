"""
Manager.

Public objects: ``PluginManager``.
"""

from __future__ import annotations

import importlib.util
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from bahram.plugins.base import BasePlugin

logger = logging.getLogger(__name__)


class PluginManager:
    """
    Plugin manager.
    """

    def __init__(self, plugin_dirs: list[str] = None) -> None:
        """
        Initialise a PluginManager instance.

        Args:
            plugin_dirs (list[str]): collection of plugin dirs. Defaults to ``None``.
        """
        self.plugin_dirs = plugin_dirs or ["plugins", "~/.bahram/plugins"]
        self.plugins: dict[str, BasePlugin] = {}
        self._hooks: dict[str, list[Callable]] = {}

    async def load_plugins(self) -> None:
        """
        Load plugins.

        Note:
            Coroutine - must be awaited.
        """
        for plugin_dir in self.plugin_dirs:
            dir_path = Path(plugin_dir).expanduser()
            if not dir_path.exists():
                continue

            for plugin_file in dir_path.glob("*.py"):
                if plugin_file.name.startswith("_"):
                    continue

                try:
                    await self._load_plugin(plugin_file)
                except Exception as e:
                    logger.error(f"Failed to load plugin {plugin_file}: {e}")

        logger.info(f"Loaded {len(self.plugins)} plugins")

    async def _load_plugin(self, plugin_file: Path) -> None:
        module_name = plugin_file.stem
        spec = importlib.util.spec_from_file_location(module_name, plugin_file)

        if spec is None or spec.loader is None:
            return

        module = importlib.util.module_from_spec(spec)
        await spec.loader.exec_module(module)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, BasePlugin) and attr is not BasePlugin:
                plugin = attr()
                self.plugins[plugin.metadata.name] = plugin
                logger.info(f"Loaded plugin: {plugin.metadata.name}")
                break

    def get_plugin(self, name: str) -> BasePlugin | None:
        """
        Return the plugin.

        Args:
            name (str): name of the object.

        Returns:
            BasePlugin | None: the resulting object, or ``None`` when it is not available.
        """
        return self.plugins.get(name)

    def list_plugins(self) -> list[str]:
        """
        List plugins.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        return list(self.plugins.keys())

    async def register_all(self, context: Any) -> None:
        """
        Register all.

        Args:
            context (Any): context.

        Note:
            Coroutine - must be awaited.
        """
        for plugin in self.plugins.values():
            try:
                await plugin.register(context)
                logger.info(f"Registered plugin: {plugin.metadata.name}")
            except Exception as e:
                logger.error(f"Failed to register plugin {plugin.metadata.name}: {e}")

    async def on_startup(self) -> None:
        """
        Hook invoked when startup.

        Note:
            Coroutine - must be awaited.
        """
        for plugin in self.plugins.values():
            try:
                await plugin.on_startup()
            except Exception as e:
                logger.error(f"Plugin startup error: {e}")

    async def on_shutdown(self) -> None:
        """
        Hook invoked when shutdown.

        Note:
            Coroutine - must be awaited.
        """
        for plugin in self.plugins.values():
            try:
                await plugin.on_shutdown()
            except Exception as e:
                logger.error(f"Plugin shutdown error: {e}")

    async def on_message(self, message: Any) -> Any | None:
        """
        Hook invoked when message.

        Args:
            message (Any): message to process.

        Returns:
            Any | None: the resulting object, or ``None`` when it is not available.

        Note:
            Coroutine - must be awaited.
        """
        for plugin in self.plugins.values():
            try:
                result = await plugin.on_message(message)
                if result is not None:
                    return result
            except Exception as e:
                logger.error(f"Plugin message error: {e}")
        return None

    async def on_tool_call(self, tool_name: str, arguments: dict) -> dict | None:
        """
        Hook invoked when tool call.

        Args:
            tool_name (str): tool name string.
            arguments (dict): mapping of arguments.

        Returns:
            dict | None: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        for plugin in self.plugins.values():
            try:
                result = await plugin.on_tool_call(tool_name, arguments)
                if result is not None:
                    return result
            except Exception as e:
                logger.error(f"Plugin tool_call error: {e}")
        return None

    async def on_tool_result(self, tool_name: str, result: Any) -> Any | None:
        """
        Hook invoked when tool result.

        Args:
            tool_name (str): tool name string.
            result (Any): result.

        Returns:
            Any | None: the resulting object, or ``None`` when it is not available.

        Note:
            Coroutine - must be awaited.
        """
        for plugin in self.plugins.values():
            try:
                new_result = await plugin.on_tool_result(tool_name, result)
                if new_result is not None:
                    return new_result
            except Exception as e:
                logger.error(f"Plugin tool_result error: {e}")
        return None

    async def on_error(self, error: Exception) -> None:
        """
        Hook invoked when error.

        Args:
            error (Exception): error.

        Note:
            Coroutine - must be awaited.
        """
        for plugin in self.plugins.values():
            try:
                await plugin.on_error(error)
            except Exception as e:
                logger.error(f"Plugin error handler error: {e}")

    def register_hook(self, event: str, callback: Callable) -> None:
        """
        Register hook.

        Args:
            event (str): event string.
            callback (Callable): callable used for callback.
        """
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(callback)

    async def dispatch_hook(self, event: str, *args, **kwargs) -> None:
        """
        Dispatch hook.

        Args:
            event (str): event string.
            *args: positional arguments forwarded to the implementation.
            **kwargs: keyword arguments forwarded to the implementation.

        Note:
            Coroutine - must be awaited.
        """
        for callback in self._hooks.get(event, []):
            try:
                await callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Hook error: {e}")
