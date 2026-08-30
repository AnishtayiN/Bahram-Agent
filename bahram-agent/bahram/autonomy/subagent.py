from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from bahram.core.engine import AgentEngine, AgentResponse, Message, MessageRole, RunConfig

logger = logging.getLogger(__name__)


class LLMProviderForSubagent(Protocol):
    async def complete(
        self, messages: list[Any], tools: list[dict[str, Any]] | None = None, **kwargs: Any
    ) -> Any: ...


@dataclass
class SubagentResult:
    task_id: str
    status: str
    summary: str
    evidence: str = ""
    artifacts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confidence: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "summary": self.summary,
            "evidence": self.evidence,
            "artifacts": self.artifacts,
            "warnings": self.warnings,
            "confidence": self.confidence,
            "metrics": self.metrics,
        }


@dataclass
class SubagentTask:
    task_id: str
    parent_run_id: str
    objective: str
    allowed_capabilities: list[str]
    allowed_tools: list[str]
    context: str = ""
    token_budget: int = 4096
    tool_budget: int = 20
    timeout_seconds: float = 120.0
    status: str = "pending"
    result: SubagentResult | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None


class SubagentEngine:
    def __init__(self, engine: AgentEngine, event_tracker: Any = None) -> None:
        self._engine = engine
        self._event_tracker = event_tracker
        self._tasks: dict[str, SubagentTask] = {}
        self._cancel_events: dict[str, asyncio.Event] = {}

    def _is_tool_allowed(self, tool_name: str, allowed: list[str]) -> bool:
        if not allowed:
            return True
        return tool_name in allowed

    async def spawn(
        self,
        parent_run_id: str,
        objective: str,
        allowed_capabilities: list[str] | None = None,
        allowed_tools: list[str] | None = None,
        context: str = "",
        model: str | None = None,
        token_budget: int = 4096,
        tool_budget: int = 20,
        timeout_seconds: float = 120.0,
    ) -> SubagentResult:
        task_id = f"sub_{uuid.uuid4().hex[:8]}"

        task = SubagentTask(
            task_id=task_id,
            parent_run_id=parent_run_id,
            objective=objective,
            allowed_capabilities=allowed_capabilities or [],
            allowed_tools=allowed_tools or [],
            context=context,
            token_budget=token_budget,
            tool_budget=tool_budget,
            timeout_seconds=timeout_seconds,
            status="running",
        )
        self._tasks[task_id] = task

        if self._event_tracker is not None and hasattr(self._event_tracker, 'emit_subagent_spawned'):
            self._event_tracker.emit_subagent_spawned(
                "", parent_run_id, task_id, {"objective": objective}
            )

        cancel_event = asyncio.Event()
        self._cancel_events[task_id] = cancel_event

        task.started_at = time.time()

        try:
            result = await asyncio.wait_for(
                self._execute_task(task, model, cancel_event),
                timeout=timeout_seconds,
            )
            task.status = "completed"
            task.result = result
        except asyncio.TimeoutError:
            result = SubagentResult(
                task_id=task_id,
                status="timeout",
                summary=f"Subagent timed out after {timeout_seconds}s",
                warnings=["Subagent execution timed out"],
            )
            task.status = "timeout"
            task.result = result
        except asyncio.CancelledError:
            result = SubagentResult(
                task_id=task_id,
                status="cancelled",
                summary="Subagent was cancelled",
                warnings=["Subagent execution was cancelled"],
            )
            task.status = "cancelled"
            task.result = result
        except Exception as e:
            result = SubagentResult(
                task_id=task_id,
                status="failed",
                summary=f"Subagent failed: {e}",
                warnings=[str(e)],
            )
            task.status = "failed"
            task.result = result
        finally:
            task.completed_at = time.time()
            self._cancel_events.pop(task_id, None)
            if self._event_tracker is not None and hasattr(self._event_tracker, 'emit_subagent_completed'):
                self._event_tracker.emit_subagent_completed(
                    "", task.parent_run_id, task_id,
                    {"status": result.status, "summary": result.summary}
                )

        return result

    async def _execute_task(
        self,
        task: SubagentTask,
        model: str | None,
        cancel_event: asyncio.Event,
    ) -> SubagentResult:
        system_prompt = (
            f"You are a subagent with a specific task. Complete it accurately and concisely.\n"
            f"Task: {task.objective}\n"
        )
        if task.context:
            system_prompt += f"\nContext:\n{task.context}\n"

        messages = [Message(role=MessageRole.SYSTEM, content=system_prompt)]

        tools_schema = self._engine.get_tools_schema()
        if task.allowed_tools:
            tools_schema = [
                t for t in tools_schema
                if t.get("function", {}).get("name", "") in task.allowed_tools
            ]

        run_cfg = RunConfig(
            max_iterations=min(task.tool_budget, 15),
            max_runtime_seconds=task.timeout_seconds,
            max_tool_calls=task.tool_budget,
            tool_timeout_seconds=min(60.0, task.timeout_seconds / 2),
        )

        provider_name = model.split("/")[0] if model and "/" in model else "anthropic"
        try:
            provider = self._engine.get_provider(model or self._engine.config.agent.model if self._engine.config else "anthropic/claude-sonnet-4-20250514")
        except (ValueError, AttributeError):
            providers = list(self._engine.providers.keys())
            if not providers:
                return SubagentResult(
                    task_id=task.task_id,
                    status="failed",
                    summary="No providers available",
                    warnings=["No LLM providers registered"],
                )
            provider = self._engine.providers[providers[0]]

        total_tool_calls = 0
        tool_results_summary = []

        for iteration in range(run_cfg.max_iterations):
            if cancel_event.is_set():
                break

            try:
                response = await provider.complete(messages, tools_schema if tools_schema else None)
            except Exception as e:
                return SubagentResult(
                    task_id=task.task_id,
                    status="failed",
                    summary=f"Provider error: {e}",
                    warnings=[str(e)],
                )

            if not response.tool_calls:
                return SubagentResult(
                    task_id=task.task_id,
                    status="completed",
                    summary=response.content or "",
                    evidence=response.content or "",
                    confidence=0.8,
                    metrics={"iterations": iteration + 1, "tool_calls": total_tool_calls},
                )

            for tool_call in response.tool_calls:
                if cancel_event.is_set():
                    break
                if total_tool_calls >= run_cfg.max_tool_calls:
                    break

                if not self._is_tool_allowed(tool_call.name, task.allowed_tools):
                    messages.append(Message(
                        role=MessageRole.TOOL,
                        content=f"Error: Tool '{tool_call.name}' is not allowed for this subagent",
                        tool_call_id=tool_call.id,
                    ))
                    continue

                executor = self._engine._tool_executor
                if executor is None:
                    from bahram.core.engine import ToolExecutor
                    executor = ToolExecutor(self._engine.tools, self._engine._approval_system)

                result = await executor.execute(tool_call, timeout=run_cfg.tool_timeout_seconds)
                total_tool_calls += 1

                tool_results_summary.append({
                    "tool": tool_call.name,
                    "success": result.success,
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

        return SubagentResult(
            task_id=task.task_id,
            status="completed",
            summary="Subagent completed with max iterations",
            evidence="",
            confidence=0.6,
            metrics={"iterations": run_cfg.max_iterations, "tool_calls": total_tool_calls},
        )

    def cancel(self, task_id: str) -> bool:
        event = self._cancel_events.get(task_id)
        if event:
            event.set()
            return True
        return False

    def get_task(self, task_id: str) -> SubagentResult | None:
        task = self._tasks.get(task_id)
        return task.result if task else None

    def list_tasks(self) -> list[dict[str, Any]]:
        return [
            {
                "task_id": t.task_id,
                "parent_run_id": t.parent_run_id,
                "objective": t.objective,
                "status": t.status,
                "created_at": t.created_at,
            }
            for t in self._tasks.values()
        ]
