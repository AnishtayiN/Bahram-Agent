from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Protocol

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
class TrajectoryStep:
    step_id: str
    iteration: int
    provider: str
    model: str
    tool_calls: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    content_length: int
    duration_ms: float
    timestamp: float
    error: str | None = None

@dataclass
class Trajectory:
    run_id: str
    session_id: str
    goal: str
    steps: list[TrajectoryStep] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    status: str = "running"
    final_content: str = ""
    total_tool_calls: int = 0
    total_duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "goal": self.goal,
            "steps": [
                {
                    "step_id": s.step_id,
                    "iteration": s.iteration,
                    "provider": s.provider,
                    "model": s.model,
                    "tool_calls": s.tool_calls,
                    "tool_results": s.tool_results,
                    "content_length": s.content_length,
                    "duration_ms": s.duration_ms,
                    "timestamp": s.timestamp,
                    "error": s.error,
                }
                for s in self.steps
            ],
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "final_content": self.final_content[:500],
            "total_tool_calls": self.total_tool_calls,
            "total_duration_ms": self.total_duration_ms,
        }

class AgentEngine:
    def __init__(self, config: Any = None) -> None:
        self.config = config
        self.providers: dict[str, LLMProvider] = {}
        self.tools: dict[str, Any] = {}
        self._running = False
        self._execution_log: list[dict[str, Any]] = []
        self._approval_system: Any = None
        self._init_approval_system()

    def _init_approval_system(self) -> None:
        try:
            from bahram.security.approval import ApprovalSystem, ApprovalConfig
            self._approval_system = ApprovalSystem(ApprovalConfig())
        except Exception as e:
            logger.warning(f"Failed to init approval system: {e}")
            self._approval_system = None

    def register_provider(self, name: str, provider: LLMProvider) -> None:
        self.providers[name] = provider
        logger.info(f"Registered provider: {name}")

    def register_tool(self, name: str, tool: Any) -> None:
        self.tools[name] = tool
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
        session_id: str = "",
    ) -> AgentResponse:
        model = model or (self.config.agent.model if self.config else "anthropic/claude-sonnet-4-20250514")
        provider = self.get_provider(model)
        tools_schema = self.get_tools_schema()
        start_time = time.time()
        run_id = str(uuid.uuid4())[:12]
        trajectory = Trajectory(run_id=run_id, session_id=session_id, goal="")

        if messages:
            for m in messages:
                if m.role == MessageRole.USER:
                    trajectory.goal = m.content[:200]
                    break

        for iteration in range(max_iterations):
            if time.time() - start_time > timeout:
                logger.warning("Agent run timed out")
                trajectory.status = "timeout"
                trajectory.finished_at = time.time()
                trajectory.total_duration_ms = (trajectory.finished_at - trajectory.started_at) * 1000
                return AgentResponse(content="Operation timed out. Please try a more specific request.")

            logger.debug(f"Agent iteration {iteration + 1}/{max_iterations}")

            step_start = time.time()
            step_id = f"step_{iteration}"

            try:
                response = await provider.complete(messages, tools_schema if tools_schema else None)
            except Exception as e:
                logger.error(f"Provider error: {e}")
                trajectory.status = "error"
                trajectory.finished_at = time.time()
                return AgentResponse(content=f"I encountered an error communicating with the model: {e}")

            if not response.tool_calls:
                trajectory.status = "completed"
                trajectory.finished_at = time.time()
                trajectory.total_duration_ms = (trajectory.finished_at - trajectory.started_at) * 1000
                trajectory.final_content = response.content
                return response

            tool_results_data = []
            for tool_call in response.tool_calls:
                result = await self.execute_tool(tool_call)
                tool_results_data.append({
                    "tool": tool_call.name,
                    "success": result.success,
                    "error": result.error,
                })
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

            step_duration = (time.time() - step_start) * 1000
            trajectory.steps.append(TrajectoryStep(
                step_id=step_id,
                iteration=iteration,
                provider=model.split("/")[0] if "/" in model else "unknown",
                model=model or "",
                tool_calls=[{"name": tc.name, "id": tc.id} for tc in response.tool_calls],
                tool_results=tool_results_data,
                content_length=len(response.content or ""),
                duration_ms=step_duration,
                timestamp=time.time(),
            ))
            trajectory.total_tool_calls += len(response.tool_calls)

        logger.warning(f"Agent reached max iterations ({max_iterations})")
        trajectory.status = "max_iterations"
        trajectory.finished_at = time.time()
        trajectory.total_duration_ms = (trajectory.finished_at - trajectory.started_at) * 1000
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

        if self._approval_system:
            is_dangerous, reason = self._approval_system.check_command(
                self._get_command_string(tool_name, tool_call.arguments)
            )
            if is_dangerous:
                risk = self._approval_system.assess_risk(
                    self._get_command_string(tool_name, tool_call.arguments)
                )
                if risk in ("critical", "high"):
                    self._log_execution(tool_name, tool_call.arguments, "blocked", reason)
                    return ToolResult(
                        tool_call_id=tool_call.id, content="", success=False,
                        error=f"Security block ({risk}): {reason}",
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

    def _get_command_string(self, tool_name: str, arguments: dict[str, Any]) -> str:
        if tool_name == "bash":
            return arguments.get("command", "")
        if tool_name == "execute_code":
            return arguments.get("code", "")
        return f"{tool_name}({json.dumps(arguments, default=str)[:200]})"

    def _log_execution(self, tool: str, args: dict, status: str, error: str | None = None) -> None:
        self._execution_log.append({
            "tool": tool, "args": args, "status": status, "error": error,
            "timestamp": time.time(),
        })
