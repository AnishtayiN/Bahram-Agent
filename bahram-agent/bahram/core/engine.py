from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger(__name__)

try:
    from bahram.platforms.circuit_breaker import CircuitBreaker
except ImportError:
    CircuitBreaker = None  # type: ignore[assignment,misc]

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

class RunState(str, Enum):
    CREATED = "created"
    LOADING = "loading"
    PLANNING = "planning"
    THINKING = "thinking"
    TOOL_PENDING = "tool_pending"
    SECURITY_CHECK = "security_check"
    TOOL_EXECUTING = "tool_executing"
    OBSERVING = "observing"
    REPLANNING = "replanning"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

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
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class AgentResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    thinking: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    state: RunState = RunState.COMPLETED

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
    state: str = ""
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
    model: str = ""
    provider: str = ""

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
                    "state": s.state,
                    "error": s.error,
                }
                for s in self.steps
            ],
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "final_content": self.final_content[:1000],
            "total_tool_calls": self.total_tool_calls,
            "total_duration_ms": self.total_duration_ms,
            "model": self.model,
            "provider": self.provider,
        }

@dataclass
class RunConfig:
    max_iterations: int = 15
    max_runtime_seconds: float = 300.0
    max_tool_calls: int = 50
    max_retries: int = 3
    tool_timeout_seconds: float = 120.0

class ToolExecutor:
    def __init__(self, tools: dict[str, Any], approval_system: Any = None) -> None:
        self.tools = tools
        self.approval_system = approval_system
        self._log: list[dict[str, Any]] = []
        self._result_cache: dict[str, ToolResult] = {}
        self._inflight: dict[str, asyncio.Event] = {}

    async def execute(self, tool_call: ToolCall, timeout: float = 120.0) -> ToolResult:
        tool_call_id = tool_call.id

        # Return cached results for already-executed tool calls (idempotency).
        if tool_call_id in self._result_cache:
            return self._result_cache[tool_call_id]

        # If another coroutine is already executing this exact tool call id,
        # wait for it and reuse its result so concurrent duplicates never
        # re-execute the tool (concurrent idempotency).
        inflight = self._inflight.get(tool_call_id)
        if inflight is not None:
            await inflight.wait()
            if tool_call_id in self._result_cache:
                return self._result_cache[tool_call_id]

        event = asyncio.Event()
        self._inflight[tool_call_id] = event
        try:
            return await self._execute_once(tool_call, timeout)
        finally:
            self._inflight.pop(tool_call_id, None)
            event.set()

    async def _execute_once(self, tool_call: ToolCall, timeout: float = 120.0) -> ToolResult:
        tool_name = tool_call.name

        if tool_name not in self.tools:
            return ToolResult(
                tool_call_id=tool_call.id, content="", success=False,
                error=f"Unknown tool: {tool_name}",
            )

        if self.approval_system:
            cmd = self._get_command_string(tool_name, tool_call.arguments)
            is_dangerous, reason = self.approval_system.check_command(cmd)
            if is_dangerous:
                risk = self.approval_system.assess_risk(cmd)
                if risk != "low":
                    self._log_event(tool_name, tool_call.arguments, "blocked", reason)
                    return ToolResult(
                        tool_call_id=tool_call.id, content="", success=False,
                        error=f"Security block ({risk}): {reason}",
                    )

        tool = self.tools[tool_name]
        try:
            if hasattr(tool, "execute"):
                result = await asyncio.wait_for(
                    tool.execute(**tool_call.arguments), timeout=timeout,
                )
                self._log_event(tool_name, tool_call.arguments, "success")
                tc_result = ToolResult(tool_call_id=tool_call.id, content=str(result), success=True)
                self._result_cache[tool_call.id] = tc_result
                return tc_result
            return ToolResult(
                tool_call_id=tool_call.id, content="", success=False,
                error=f"Tool '{tool_name}' has no execute method",
            )
        except asyncio.TimeoutError:
            self._log_event(tool_name, tool_call.arguments, "timeout")
            return ToolResult(
                tool_call_id=tool_call.id, content="", success=False,
                error=f"Tool '{tool_name}' timed out after {timeout}s",
            )
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            self._log_event(tool_name, tool_call.arguments, "error", str(e))
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

    def _log_event(self, tool: str, args: dict, status: str, error: str | None = None) -> None:
        self._log.append({
            "tool": tool, "args": args, "status": status, "error": error,
            "timestamp": time.time(),
        })

class AgentEngine:
    def __init__(self, config: Any = None) -> None:
        self.config = config
        self.providers: dict[str, LLMProvider] = {}
        self.tools: dict[str, Any] = {}
        self._cancel_event = asyncio.Event()
        self._approval_system: Any = None
        self._tool_executor: ToolExecutor | None = None
        self._circuit_breaker: Any = None
        self._budget_manager: Any = None
        self._event_tracker: Any = None
        if CircuitBreaker is not None:
            self._circuit_breaker = CircuitBreaker()
        self._init_approval_system()

    def _init_approval_system(self) -> None:
        try:
            from bahram.security.approval import ApprovalConfig, ApprovalSystem
            self._approval_system = ApprovalSystem(ApprovalConfig())
        except Exception as e:
            logger.warning(f"Failed to init approval system: {e}")
            self._approval_system = None

    def set_budget_manager(self, budget_manager: Any) -> None:
        self._budget_manager = budget_manager

    def set_event_tracker(self, event_tracker: Any) -> None:
        self._event_tracker = event_tracker

    def set_trajectory_dir(self, trajectory_dir: str) -> None:
        self._trajectory_dir = trajectory_dir

    def _persist_trajectory(self, trajectory: Trajectory) -> None:
        trajectory_dir = getattr(self, '_trajectory_dir', 'data/trajectories')
        try:
            os.makedirs(trajectory_dir, exist_ok=True)
            path = os.path.join(trajectory_dir, f"{trajectory.run_id}.json")
            with open(path, 'w') as f:
                json.dump(trajectory.to_dict(), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist trajectory: {e}")

    def register_provider(self, name: str, provider: LLMProvider) -> None:
        self.providers[name] = provider
        logger.info(f"Registered provider: {name}")

    def register_tool(self, name: str, tool: Any) -> None:
        self.tools[name] = tool
        self._tool_executor = ToolExecutor(self.tools, self._approval_system)
        logger.info(f"Registered tool: {name}")

    def get_provider(self, model: str) -> LLMProvider:
        provider_name = model.split("/")[0] if "/" in model else "anthropic"

        if provider_name in self.providers:
            if self._circuit_breaker is not None:
                can_exec, reason = self._circuit_breaker.can_execute(provider_name)
                if not can_exec:
                    logger.warning(f"Circuit open for {provider_name}: {reason}")
                    return self._get_fallback_provider(provider_name)
            return self.providers[provider_name]

        return self._get_fallback_provider(provider_name)

    def _get_fallback_provider(self, failed_provider: str) -> LLMProvider:
        if "__fallback__" in self.providers:
            logger.info(f"Using fallback provider (primary '{failed_provider}' unavailable)")
            return self.providers["__fallback__"]
        if self.providers:
            first = next(iter(self.providers.values()))
            logger.info("No fallback registered, using first available provider")
            return first
        raise ValueError(f"Provider '{failed_provider}' not registered and no fallback available")

    def record_provider_success(self, provider_name: str) -> None:
        if self._circuit_breaker is not None:
            self._circuit_breaker.record_success(provider_name)

    def record_provider_failure(self, provider_name: str) -> None:
        if self._circuit_breaker is not None:
            self._circuit_breaker.record_failure(provider_name)
        if self._event_tracker is not None and hasattr(self._event_tracker, 'emit_provider_fallback'):
            self._event_tracker.emit_provider_fallback(
                "", "", {"provider": provider_name, "reason": "circuit_breaker", "message": f"Provider {provider_name} failed"}
            )

    def get_tools_schema(self) -> list[dict[str, Any]]:
        schemas = []
        for name, tool in self.tools.items():
            if hasattr(tool, "schema"):
                schemas.append(tool.schema())
        return schemas

    def cancel(self) -> None:
        self._cancel_event.set()

    def reset_cancel(self) -> None:
        self._cancel_event.clear()

    def _get_run_config(self) -> RunConfig:
        if self.config and hasattr(self.config, 'agent'):
            return RunConfig(
                max_iterations=getattr(self.config.agent, 'max_iterations', 15),
                max_runtime_seconds=getattr(self.config.agent, 'max_runtime_seconds', 300.0),
                max_tool_calls=getattr(self.config.agent, 'max_tool_calls', 50),
                tool_timeout_seconds=getattr(self.config.tools, 'bash_timeout', 120.0),
            )
        return RunConfig()

    async def run(
        self, messages: list[Message], model: str | None = None,
        session_id: str = "",
    ) -> AgentResponse:
        run_cfg = self._get_run_config()
        model = model or (self.config.agent.model if self.config else "anthropic/claude-sonnet-4-20250514")
        provider_name = model.split("/")[0] if "/" in model else "anthropic"
        provider = self.get_provider(model)
        tools_schema = self.get_tools_schema()
        start_time = time.time()
        run_id = str(uuid.uuid4())[:12]
        self.reset_cancel()

        trajectory = Trajectory(
            run_id=run_id, session_id=session_id, goal="",
            model=model, provider=provider_name,
        )

        if messages:
            for m in messages:
                if m.role == MessageRole.USER:
                    trajectory.goal = m.content[:200]
                    break

        total_tool_calls = 0

        for iteration in range(run_cfg.max_iterations):
            if self._cancel_event.is_set():
                trajectory.status = "cancelled"
                trajectory.finished_at = time.time()
                trajectory.total_duration_ms = (trajectory.finished_at - trajectory.started_at) * 1000
                self._persist_trajectory(trajectory)
                return AgentResponse(content="Operation cancelled.", state=RunState.CANCELLED)

            if time.time() - start_time > run_cfg.max_runtime_seconds:
                trajectory.status = "timeout"
                trajectory.finished_at = time.time()
                trajectory.total_duration_ms = (trajectory.finished_at - trajectory.started_at) * 1000
                self._persist_trajectory(trajectory)
                return AgentResponse(content="Operation timed out. Please try a more specific request.", state=RunState.TIMEOUT)

            if self._budget_manager is not None:
                budget_result = self._budget_manager.check_budget(run_id)
                if not budget_result.get("can_continue", True):
                    reason = "Budget limit exceeded: " + ", ".join(budget_result.get("exceeded", []))
                    logger.warning(f"Budget exceeded: {reason}")
                    if self._event_tracker is not None and hasattr(self._event_tracker, 'emit_budget_exceeded'):
                        self._event_tracker.emit_budget_exceeded(session_id, run_id, {"reason": reason})
                    trajectory.status = "budget_exceeded"
                    trajectory.finished_at = time.time()
                    trajectory.total_duration_ms = (trajectory.finished_at - trajectory.started_at) * 1000
                    self._persist_trajectory(trajectory)
                    return AgentResponse(
                        content=f"Budget limit reached: {reason}",
                        state=RunState.COMPLETED,
                    )

            logger.debug(f"Agent iteration {iteration + 1}/{run_cfg.max_iterations}")
            step_start = time.time()
            step_id = f"step_{iteration}"

            try:
                response = await provider.complete(messages, tools_schema if tools_schema else None)
                self.record_provider_success(provider_name)
            except Exception as e:
                logger.error(f"Provider error: {e}")
                self.record_provider_failure(provider_name)
                fallback_provider = self._get_fallback_provider(provider_name)
                if fallback_provider is not provider:
                    try:
                        response = await fallback_provider.complete(messages, tools_schema if tools_schema else None)
                    except Exception as e2:
                        logger.error(f"Fallback also failed: {e2}")
                        trajectory.status = "error"
                        trajectory.finished_at = time.time()
                        self._persist_trajectory(trajectory)
                        return AgentResponse(content=f"I encountered an error communicating with the model: {e2}", state=RunState.FAILED)
                else:
                    trajectory.status = "error"
                    trajectory.finished_at = time.time()
                    self._persist_trajectory(trajectory)
                    return AgentResponse(content=f"I encountered an error communicating with the model: {e}", state=RunState.FAILED)

            if self._budget_manager is not None:
                usage_tokens = len(response.content or "") // 4
                if response.tool_calls:
                    usage_tokens += sum(len(json.dumps(tc.arguments)) // 4 for tc in response.tool_calls)
                self._budget_manager.record_model_call(
                    run_id,
                    input_tokens=usage_tokens // 2,
                    output_tokens=usage_tokens // 2,
                    model=model or "",
                )

            if not response.tool_calls:
                trajectory.status = "completed"
                trajectory.finished_at = time.time()
                trajectory.total_duration_ms = (trajectory.finished_at - trajectory.started_at) * 1000
                trajectory.final_content = response.content
                self._persist_trajectory(trajectory)
                return AgentResponse(
                    content=response.content, state=RunState.COMPLETED,
                    metadata={"trajectory": trajectory.to_dict()},
                )

            tool_results_data = []
            for tool_call in response.tool_calls:
                if self._cancel_event.is_set():
                    break
                if total_tool_calls >= run_cfg.max_tool_calls:
                    trajectory.status = "max_tool_calls"
                    trajectory.finished_at = time.time()
                    trajectory.total_duration_ms = (trajectory.finished_at - trajectory.started_at) * 1000
                    self._persist_trajectory(trajectory)
                    return AgentResponse(
                        content=f"Reached maximum tool calls ({run_cfg.max_tool_calls}). Here's what I've done so far.",
                        state=RunState.COMPLETED,
                    )

                if self._tool_executor is None:
                    self._tool_executor = ToolExecutor(self.tools, self._approval_system)
                result = await self._tool_executor.execute(tool_call, timeout=run_cfg.tool_timeout_seconds)
                total_tool_calls += 1

                if self._budget_manager is not None:
                    self._budget_manager.record_tool_call(run_id, tool_name=tool_call.name)

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
                provider=trajectory.provider,
                model=model or "",
                tool_calls=[{"name": tc.name, "id": tc.id} for tc in response.tool_calls],
                tool_results=tool_results_data,
                content_length=len(response.content or ""),
                duration_ms=step_duration,
                timestamp=time.time(),
                state=RunState.TOOL_EXECUTING.value,
            ))
            trajectory.total_tool_calls += len(response.tool_calls)

        logger.warning(f"Agent reached max iterations ({run_cfg.max_iterations})")
        trajectory.status = "max_iterations"
        trajectory.finished_at = time.time()
        trajectory.total_duration_ms = (trajectory.finished_at - trajectory.started_at) * 1000
        self._persist_trajectory(trajectory)
        return AgentResponse(
            content="I've reached the maximum number of iterations. Let me summarize what I've accomplished so far.",
            state=RunState.COMPLETED,
        )

    async def run_streaming(
        self, messages: list[Message], model: str | None = None,
    ) -> AsyncIterator[str]:
        run_cfg = self._get_run_config()
        model = model or (self.config.agent.model if self.config else "anthropic/claude-sonnet-4-20250514")
        provider_name = model.split("/")[0] if "/" in model else "anthropic"
        provider = self.get_provider(model)
        tools_schema = self.get_tools_schema()
        start_time = time.time()

        for iteration in range(run_cfg.max_iterations):
            if self._cancel_event.is_set():
                yield "Operation cancelled."
                return
            if time.time() - start_time > run_cfg.max_runtime_seconds:
                yield "Operation timed out."
                return

            full_content = ""
            try:
                async for chunk in provider.stream(messages, tools_schema if tools_schema else None):
                    full_content += chunk
                    yield chunk
                self.record_provider_success(provider_name)
            except Exception:
                self.record_provider_failure(provider_name)
                try:
                    provider = self.get_provider(model)
                    async for chunk in provider.stream(messages, tools_schema if tools_schema else None):
                        full_content += chunk
                        yield chunk
                except Exception as e2:
                    yield f"\nError: {e2}"
                    return

            if not full_content:
                return

            if not tools_schema:
                return

            messages.append(Message(role=MessageRole.ASSISTANT, content=full_content))
