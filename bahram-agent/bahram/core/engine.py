from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional, Protocol

from bahram.core.config import Config

logger = logging.getLogger(__name__)

class MessageRole(str, Enum):
    ""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

@dataclass
class Message:
    ""

    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ToolCall:
    ""

    id: str
    name: str
    arguments: dict[str, Any]

@dataclass
class ToolResult:
    ""

    tool_call_id: str
    content: str
    success: bool
    error: Optional[str] = None

@dataclass
class AgentResponse:
    ""

    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    thinking: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

class LLMProvider(Protocol):
    ""

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AgentResponse:
        ""
        ...

    async def stream(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        ""
        ...

class AgentEngine:
    ""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.providers: dict[str, LLMProvider] = {}
        self.tools: dict[str, Any] = {}
        self._running = False

    def register_provider(self, name: str, provider: LLMProvider) -> None:
        ""
        self.providers[name] = provider
        logger.info(f"Registered provider: {name}")

    def register_tool(self, name: str, tool: Any) -> None:
        ""
        self.tools[name] = tool
        logger.info(f"Registered tool: {name}")

    def get_provider(self, model: str) -> LLMProvider:
        ""
        provider_name = model.split("/")[0] if "/" in model else "anthropic"
        if provider_name not in self.providers:
            raise ValueError(f"Provider '{provider_name}' not registered")
        return self.providers[provider_name]

    def get_tools_schema(self) -> list[dict[str, Any]]:
        ""
        schemas = []
        for name, tool in self.tools.items():
            if hasattr(tool, "schema"):
                schemas.append(tool.schema())
        return schemas

    async def run(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        max_iterations: int = 10,
    ) -> AgentResponse:
        ""
        model = model or self.config.agent.model
        provider = self.get_provider(model)
        tools_schema = self.get_tools_schema()

        for iteration in range(max_iterations):
            logger.debug(f"Agent iteration {iteration + 1}/{max_iterations}")

            response = await provider.complete(messages, tools_schema)

            if not response.tool_calls:
                return response

            for tool_call in response.tool_calls:
                result = await self.execute_tool(tool_call)
                messages.append(
                    Message(
                        role=MessageRole.TOOL,
                        content=result.content,
                        tool_call_id=result.tool_call_id,
                    )
                )

            messages.append(
                Message(
                    role=MessageRole.ASSISTANT,
                    content=response.content or "",
                    metadata={"tool_calls": response.tool_calls},
                )
            )

        logger.warning(f"Agent reached max iterations ({max_iterations})")
        return AgentResponse(content="I've reached the maximum number of iterations.")

    async def run_streaming(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        max_iterations: int = 10,
    ) -> AsyncIterator[str]:
        ""
        model = model or self.config.agent.model
        provider = self.get_provider(model)
        tools_schema = self.get_tools_schema()

        for iteration in range(max_iterations):
            full_content = ""
            tool_calls: list[ToolCall] = []

            async for chunk in provider.stream(messages, tools_schema):
                if chunk.startswith("[TOOL_CALL:"):

                    tool_call = self._parse_tool_call(chunk)
                    if tool_call:
                        tool_calls.append(tool_call)
                else:
                    full_content += chunk
                    yield chunk

            if not tool_calls:
                return

            for tool_call in tool_calls:
                result = await self.execute_tool(tool_call)
                messages.append(
                    Message(
                        role=MessageRole.TOOL,
                        content=result.content,
                        tool_call_id=result.tool_call_id,
                    )
                )

            messages.append(
                Message(
                    role=MessageRole.ASSISTANT,
                    content=full_content,
                    metadata={"tool_calls": tool_calls},
                )
            )

    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        ""
        tool_name = tool_call.name

        if tool_name not in self.tools:
            return ToolResult(
                tool_call_id=tool_call.id,
                content="",
                success=False,
                error=f"Unknown tool: {tool_name}",
            )

        tool = self.tools[tool_name]

        try:
            if hasattr(tool, "execute"):
                result = await tool.execute(**tool_call.arguments)
                return ToolResult(
                    tool_call_id=tool_call.id,
                    content=str(result),
                    success=True,
                )
            else:
                return ToolResult(
                    tool_call_id=tool_call.id,
                    content="",
                    success=False,
                    error=f"Tool '{tool_name}' has no execute method",
                )
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return ToolResult(
                tool_call_id=tool_call.id,
                content="",
                success=False,
                error=str(e),
            )

    def _parse_tool_call(self, raw: str) -> Optional[ToolCall]:
        ""

        import json
        import re

        match = re.match(r"\[TOOL_CALL:(\w+):(.+?)\]", raw)
        if match:
            name = match.group(1)
            try:
                args = json.loads(match.group(2))
                return ToolCall(
                    id=f"call_{int(time.time() * 1000)}",
                    name=name,
                    arguments=args,
                )
            except json.JSONDecodeError:
                pass
        return None
