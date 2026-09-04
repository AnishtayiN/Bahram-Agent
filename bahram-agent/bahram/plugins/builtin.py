"""
Builtin.

Public objects: ``BuiltInPlugin``, ``LoggingPlugin``, ``MetricsPlugin``, ``CachePlugin``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class BuiltInPlugin:
    """
    Built in plugin.
    """

    def __init__(self) -> None:
        """
        Initialise a BuiltInPlugin instance.
        """
        self.name = ""
        self.description = ""
        self.enabled = True

    async def on_message(self, message: dict) -> dict:
        """
        Hook invoked when message.

        Args:
            message (dict): message to process.

        Returns:
            dict: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        return message

    async def on_response(self, response: str) -> str:
        """
        Hook invoked when response.

        Args:
            response (str): response string.

        Returns:
            str: the rendered string.

        Note:
            Coroutine - must be awaited.
        """
        return response

    async def on_tool_call(self, tool: str, args: dict) -> dict:
        """
        Hook invoked when tool call.

        Args:
            tool (str): tool string.
            args (dict): positional arguments forwarded to the implementation.

        Returns:
            dict: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        return args

    async def on_error(self, error: Exception) -> None:
        """
        Hook invoked when error.

        Default: no-op. Subclasses override the hooks they care about.

        Args:
            error (Exception): error.

        Note:
            Coroutine - must be awaited.
        """
        pass


class LoggingPlugin(BuiltInPlugin):
    """
    Logging plugin.
    """

    def __init__(self) -> None:
        """
        Initialise a LoggingPlugin instance.
        """
        super().__init__()
        self.name = "logging"
        self.description = "Log all interactions"

    async def on_message(self, message: dict) -> dict:
        """
        Hook invoked when message.

        Args:
            message (dict): message to process.

        Returns:
            dict: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        logger.debug(f"Message: {message.get('role', 'unknown')}")
        return message

    async def on_response(self, response: str) -> str:
        """
        Hook invoked when response.

        Args:
            response (str): response string.

        Returns:
            str: the rendered string.

        Note:
            Coroutine - must be awaited.
        """
        logger.debug(f"Response: {response[:100]}...")
        return response


class MetricsPlugin(BuiltInPlugin):
    """
    Metrics plugin.
    """

    def __init__(self) -> None:
        """
        Initialise a MetricsPlugin instance.
        """
        super().__init__()
        self.name = "metrics"
        self.description = "Collect usage metrics"
        self._metrics: dict[str, int] = {
            "messages": 0,
            "responses": 0,
            "tool_calls": 0,
            "errors": 0,
        }

    async def on_message(self, message: dict) -> dict:
        """
        Hook invoked when message.

        Args:
            message (dict): message to process.

        Returns:
            dict: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        self._metrics["messages"] += 1
        return message

    async def on_response(self, response: str) -> str:
        """
        Hook invoked when response.

        Args:
            response (str): response string.

        Returns:
            str: the rendered string.

        Note:
            Coroutine - must be awaited.
        """
        self._metrics["responses"] += 1
        return response

    async def on_tool_call(self, tool: str, args: dict) -> dict:
        """
        Hook invoked when tool call.

        Args:
            tool (str): tool string.
            args (dict): positional arguments forwarded to the implementation.

        Returns:
            dict: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        self._metrics["tool_calls"] += 1
        return args

    async def on_error(self, error: Exception) -> None:
        """
        Hook invoked when error.

        Args:
            error (Exception): error.

        Note:
            Coroutine - must be awaited.
        """
        self._metrics["errors"] += 1

    def get_metrics(self) -> dict:
        """
        Return the metrics.

        Returns:
            dict: a mapping of str, Any.
        """
        return self._metrics.copy()


class CachePlugin(BuiltInPlugin):
    """
    Cache plugin.
    """

    def __init__(self) -> None:
        """
        Initialise a CachePlugin instance.
        """
        super().__init__()
        self.name = "cache"
        self.description = "Cache frequent responses"
        self._cache: dict[str, str] = {}

    async def on_message(self, message: dict) -> dict:
        """
        Hook invoked when message.

        Args:
            message (dict): message to process.

        Returns:
            dict: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        content = message.get("content", "")
        if content in self._cache:
            message["_cached_response"] = self._cache[content]
        return message

    async def on_response(self, response: str) -> str:
        """
        Hook invoked when response.

        Args:
            response (str): response string.

        Returns:
            str: the rendered string.

        Note:
            Coroutine - must be awaited.
        """
        return response


BUILTIN_PLUGINS = {
    "logging": LoggingPlugin,
    "metrics": MetricsPlugin,
    "cache": CachePlugin,
}
