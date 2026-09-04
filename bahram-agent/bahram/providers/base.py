"""
Base.

Public objects: ``BaseProvider``.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from bahram.core.engine import AgentResponse, Message, MessageRole, ToolCall

logger = logging.getLogger(__name__)


class BaseProvider(ABC):
    """
    Base provider.
    """

    def __init__(self, api_key: str = "", model: str = "", **kwargs: Any) -> None:
        """
        Initialise a BaseProvider instance.

        Args:
            api_key (str): api key string. Defaults to ``''``.
            model (str): model identifier in ``provider/model`` form. Defaults to ``''``.
            **kwargs (Any): keyword arguments forwarded to the implementation.
        """
        self.api_key = api_key
        self.model = model
        self._extra = kwargs

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> AgentResponse:
        """
        Complete.

        Args:
            messages (list[Message]): chat messages to send to the model.
            tools (list[dict[str, Any]] | None): collection of tools. Defaults to ``None``.
            model (str | None): model identifier in ``provider/model`` form. Defaults to ``None``.
            temperature (float): numeric value for temperature. Defaults to ``0.7``.
            max_tokens (int): numeric value for max tokens. Defaults to ``4096``.
            **kwargs (Any): keyword arguments forwarded to the implementation.

        Returns:
            AgentResponse: the resulting AgentResponse.

        Note:
            Coroutine - must be awaited.
        """
        raw_messages, system_msg = self._prepare_messages(messages)
        tool_schemas = self._prepare_tools(tools)
        return await self._call_api(
            raw_messages, system_msg, tool_schemas, model, temperature, max_tokens
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Stream.

        Args:
            messages (list[Message]): chat messages to send to the model.
            tools (list[dict[str, Any]] | None): collection of tools. Defaults to ``None``.
            model (str | None): model identifier in ``provider/model`` form. Defaults to ``None``.
            temperature (float): numeric value for temperature. Defaults to ``0.7``.
            max_tokens (int): numeric value for max tokens. Defaults to ``4096``.
            **kwargs (Any): keyword arguments forwarded to the implementation.

        Returns:
            AsyncIterator[str]: the resulting AsyncIterator[str].

        Note:
            Coroutine - must be awaited.
        """
        raw_messages, system_msg = self._prepare_messages(messages)
        tool_schemas = self._prepare_tools(tools)
        async for chunk in self._stream_api(
            raw_messages, system_msg, tool_schemas, model, temperature, max_tokens
        ):
            yield chunk

    def _prepare_messages(self, messages: list[Message]) -> tuple[list[dict], str]:
        raw = []
        system_msg = ""
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_msg = msg.content
                continue
            if msg.role == MessageRole.TOOL:
                raw.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id or "",
                        "content": msg.content,
                    }
                )
            elif msg.role == MessageRole.ASSISTANT:
                entry: dict[str, Any] = {"role": "assistant", "content": msg.content}
                if msg.metadata and "tool_calls" in msg.metadata:
                    tc_list = msg.metadata["tool_calls"]
                    entry["tool_calls"] = [
                        {
                            "id": tc.id if hasattr(tc, "id") else tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc.name if hasattr(tc, "name") else tc.get("name", ""),
                                "arguments": json.dumps(
                                    tc.arguments
                                    if hasattr(tc, "arguments")
                                    else tc.get("arguments", {})
                                ),
                            },
                        }
                        for tc in tc_list
                    ]
                    if not entry["content"]:
                        entry["content"] = None
                raw.append(entry)
            else:
                raw.append({"role": msg.role.value, "content": msg.content})
        return raw, system_msg

    def _prepare_tools(self, tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        if not tools:
            return []
        formatted = []
        for t in tools:
            if "type" in t:
                formatted.append(t)
            elif "name" in t:
                formatted.append(
                    {
                        "type": "function",
                        "function": {
                            "name": t["name"],
                            "description": t.get("description", ""),
                            "parameters": t.get("parameters", {}),
                        },
                    }
                )
            else:
                formatted.append(t)
        return formatted

    @abstractmethod
    async def _call_api(
        self,
        messages: list[dict],
        system_msg: str,
        tools: list[dict[str, Any]],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> AgentResponse:
        """Perform the provider specific HTTP request.

        Subclasses implement the wire protocol here;
        :meth:`BaseProvider.complete` takes care of message formatting,
        retries and error translation.

        Args:
            messages (list[dict]): OpenAI-style message payload.
            system_msg (str): system prompt extracted from the history.
            tools (list[dict[str, Any]]): tool schemas to advertise.
            model (str | None): model id, or ``None`` to use the default.
            temperature (float): sampling temperature.
            max_tokens (int): maximum number of tokens to generate.

        Returns:
            AgentResponse: normalised response.

        Raises:
            Exception: HTTP and transport errors; the base class converts them
                into a retry/failover decision.

        Note:
            Coroutine - must be awaited.
        """
        ...

    async def _stream_api(
        self,
        messages: list[dict],
        system_msg: str,
        tools: list[dict[str, Any]],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        yield ""

    def _parse_openai_response(self, data: dict) -> AgentResponse:
        choice = data.get("choices", [{}])[0]
        msg = choice.get("message", {})
        content = msg.get("content") or ""
        raw_tool_calls = msg.get("tool_calls") or []
        tool_calls = []
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", f"call_{int(time.time() * 1000)}"),
                    name=func.get("name", ""),
                    arguments=args,
                )
            )
        return AgentResponse(content=content, tool_calls=tool_calls)

    def _get_model(self, model: str | None) -> str:
        return model or self.model

    def get_models(self) -> list[str]:
        """
        Return the models.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        return []

    def get_provider_info(self) -> dict[str, Any]:
        """
        Return the provider info.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {"name": self.__class__.__name__, "configured": bool(self.api_key)}
