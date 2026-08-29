from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional, Protocol

logger = logging.getLogger(__name__)

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

@dataclass
class Message:
    role: MessageRole
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

@dataclass
class ToolResult:
    tool_call_id: str
    content: str
    success: bool
    error: str | None = None

@dataclass
class AgentResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    thinking: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

class LLMProvider(Protocol):
    async def complete(
        self, messages: list[Message], tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AgentResponse: ...

    async def stream(
        self, messages: list[Message], tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]: ...

@dataclass
class ToolMeta:
    name: str
    description: str
    risk_level: str = "safe"
    requires_approval: bool = False
    network_access: bool = False
    filesystem_access: bool = False
    shell_access: bool = False

class SecurityPolicy:
    def __init__(self) -> None:
        self._blocked_commands: list[str] = ["rm -rf /", "mkfs", ":(){ :|:& };:"]
        self._approval_required_tools: list[str] = ["bash", "write", "edit", "execute_code"]

    def check_tool(self, tool_name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
        if tool_name in self._approval_required_tools:
            if tool_name == "bash":
                cmd = arguments.get("command", "")
                for blocked in self._blocked_commands:
                    if blocked in cmd:
                        return False, f"Blocked dangerous command: {blocked}"
            return True, "approval_required"
        return True, "ok"

    def requires_approval(self, tool_name: str) -> bool:
        return tool_name in self._approval_required_tools

class AgentEngine:
    def __init__(self, config: Any = None) -> None:
        self.config = config
        self.providers: dict[str, LLMProvider] = {}
        self.tools: dict[str, Any] = {}
        self.tool_meta: dict[str, ToolMeta] = {}
        self.security = SecurityPolicy()
        self._running = False
        self._execution_log: list[dict[str, Any]] = []

    def register_provider(self, name: str, provider: LLMProvider) -> None:
        self.providers[name] = provider
        logger.info(f"Registered provider: {name}")

    def register_tool(self, name: str, tool: Any, meta: ToolMeta | None = None) -> None:
        self.tools[name] = tool
        if meta:
            self.tool_meta[name] = meta
        logger.info(f"Registered tool: {name}")

    def get_provider(self, model: str) -> LLMProvider:
        provider_name = model.split("/")[0] if "/" in model else "anthropic"
        if provider_name not in self.providers:
            raise ValueError(f"Provider '{provider_name}' not registered")
        return self.providers[provider_name]

    def get_tools_schema(self) -> list[dict[str, Any]]:
        schemas = []
        for name, tool in self.tools.items():
            if hasattr(tool, "schema"):
                schemas.append(tool.schema())
        return schemas

    async def run(
        self, messages: list[Message], model: str | None = None,
        max_iterations: int = 15, timeout: float = 300.0,
    ) -> AgentResponse:
        model = model or (self.config.agent.model if self.config else "anthropic/claude-sonnet-4-20250514")
        provider = self.get_provider(model)
        tools_schema = self.get_tools_schema()
        start_time = time.time()

        for iteration in range(max_iterations):
            if time.time() - start_time > timeout:
                logger.warning("Agent run timed out")
                return AgentResponse(content="Operation timed out. Please try a more specific request.")

            logger.debug(f"Agent iteration {iteration + 1}/{max_iterations}")

            try:
                response = await provider.complete(messages, tools_schema if tools_schema else None)
            except Exception as e:
                logger.error(f"Provider error: {e}")
                return AgentResponse(content=f"I encountered an error communicating with the model: {e}")

            if not response.tool_calls:
                return response

            for tool_call in response.tool_calls:
                result = await self.execute_tool(tool_call)
                messages.append(Message(
                    role=MessageRole.TOOL,
                    content=result.content if result.success else f"Error: {result.error}",
                    tool_call_id=result.tool_call_id,
                ))

            messages.append(Message(
                role=MessageRole.ASSISTANT,
                content=response.content or "",
                metadata={"tool_calls": response.tool_calls} if response.tool_calls else {},
            ))

        logger.warning(f"Agent reached max iterations ({max_iterations})")
        return AgentResponse(content="I've reached the maximum number of iterations. Let me summarize what I've accomplished so far.")

    async def run_streaming(
        self, messages: list[Message], model: str | None = None,
        max_iterations: int = 15, timeout: float = 300.0,
    ) -> AsyncIterator[str]:
        model = model or (self.config.agent.model if self.config else "anthropic/claude-sonnet-4-20250514")
        provider = self.get_provider(model)
        tools_schema = self.get_tools_schema()
        start_time = time.time()

        for iteration in range(max_iterations):
            if time.time() - start_time > timeout:
                yield "Operation timed out."
                return

            full_content = ""
            try:
                async for chunk in provider.stream(messages, tools_schema if tools_schema else None):
                    full_content += chunk
                    yield chunk
            except Exception as e:
                yield f"\nError: {e}"
                return

            if not full_content:
                return

            if not tools_schema:
                return

            messages.append(Message(role=MessageRole.ASSISTANT, content=full_content))

    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        tool_name = tool_call.name

        if tool_name not in self.tools:
            return ToolResult(
                tool_call_id=tool_call.id, content="", success=False,
                error=f"Unknown tool: {tool_name}",
            )

        is_safe, reason = self.security.check_tool(tool_name, tool_call.arguments)
        if not is_safe:
            self._log_execution(tool_name, tool_call.arguments, "blocked", reason)
            return ToolResult(
                tool_call_id=tool_call.id, content="", success=False,
                error=f"Security block: {reason}",
            )

        tool = self.tools[tool_name]
        try:
            if hasattr(tool, "execute"):
                result = await asyncio.wait_for(
                    tool.execute(**tool_call.arguments), timeout=120.0,
                )
                self._log_execution(tool_name, tool_call.arguments, "success")
                return ToolResult(tool_call_id=tool_call.id, content=str(result), success=True)
            return ToolResult(
                tool_call_id=tool_call.id, content="", success=False,
                error=f"Tool '{tool_name}' has no execute method",
            )
        except asyncio.TimeoutError:
            self._log_execution(tool_name, tool_call.arguments, "timeout")
            return ToolResult(
                tool_call_id=tool_call.id, content="", success=False,
                error=f"Tool '{tool_name}' timed out after 120s",
            )
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            self._log_execution(tool_name, tool_call.arguments, "error", str(e))
            return ToolResult(
                tool_call_id=tool_call.id, content="", success=False,
                error=str(e),
            )

    def _log_execution(self, tool: str, args: dict, status: str, error: str | None = None) -> None:
        self._execution_log.append({
            "tool": tool, "args": args, "status": status, "error": error,
            "timestamp": time.time(),
        })
