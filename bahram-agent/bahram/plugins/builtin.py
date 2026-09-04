from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

class BuiltInPlugin:

    def __init__(self) -> None:
        self.name = ""
        self.description = ""
        self.enabled = True

    async def on_message(self, message: dict) -> dict:
        return message

    async def on_response(self, response: str) -> str:
        return response

    async def on_tool_call(self, tool: str, args: dict) -> dict:
        return args

    async def on_error(self, error: Exception) -> None:
        pass

class LoggingPlugin(BuiltInPlugin):

    def __init__(self) -> None:
        super().__init__()
        self.name = "logging"
        self.description = "Log all interactions"

    async def on_message(self, message: dict) -> dict:
        logger.debug(f"Message: {message.get('role', 'unknown')}")
        return message

    async def on_response(self, response: str) -> str:
        logger.debug(f"Response: {response[:100]}...")
        return response

class MetricsPlugin(BuiltInPlugin):

    def __init__(self) -> None:
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
        self._metrics["messages"] += 1
        return message

    async def on_response(self, response: str) -> str:
        self._metrics["responses"] += 1
        return response

    async def on_tool_call(self, tool: str, args: dict) -> dict:
        self._metrics["tool_calls"] += 1
        return args

    async def on_error(self, error: Exception) -> None:
        self._metrics["errors"] += 1

    def get_metrics(self) -> dict:
        return self._metrics.copy()

class CachePlugin(BuiltInPlugin):

    def __init__(self) -> None:
        super().__init__()
        self.name = "cache"
        self.description = "Cache frequent responses"
        self._cache: dict[str, str] = {}

    async def on_message(self, message: dict) -> dict:
        content = message.get("content", "")
        if content in self._cache:
            message["_cached_response"] = self._cache[content]
        return message

    async def on_response(self, response: str) -> str:
        return response

BUILTIN_PLUGINS = {
    "logging": LoggingPlugin,
    "metrics": MetricsPlugin,
    "cache": CachePlugin,
}
