"""Delegation tool for Bahram Agent."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class SubAgent:
    """A spawned subagent."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task: str = ""
    status: str = "pending"
    result: Optional[str] = None
    error: Optional[str] = None
    context: dict[str, Any] = field(default_factory=dict)


class DelegationTool:
    """Spawn isolated subagents for parallel work."""

    def __init__(self) -> None:
        self._subagents: dict[str, SubAgent] = {}
        self._task_fn: Optional[Callable] = None

    def set_task_fn(self, fn: Callable) -> None:
        """Set the function to execute tasks."""
        self._task_fn = fn

    async def delegate(
        self,
        task: str,
        context: dict[str, Any] = None,
    ) -> SubAgent:
        """Delegate a task to a subagent."""
        agent = SubAgent(
            task=task,
            context=context or {},
        )
        self._subagents[agent.id] = agent

        # Execute in background
        asyncio.create_task(self._run_agent(agent))

        return agent

    async def _run_agent(self, agent: SubAgent) -> None:
        """Run a subagent."""
        agent.status = "running"

        try:
            if self._task_fn:
                result = await self._task_fn(agent.task, agent.context)
                agent.result = result
                agent.status = "completed"
            else:
                agent.error = "No task function configured"
                agent.status = "failed"
        except Exception as e:
            agent.error = str(e)
            agent.status = "failed"

    def get_agent(self, agent_id: str) -> Optional[SubAgent]:
        """Get a subagent by ID."""
        return self._subagents.get(agent_id)

    def list_agents(self) -> list[SubAgent]:
        """List all subagents."""
        return list(self._subagents.values())

    def render_status(self) -> str:
        """Render status of all subagents."""
        if not self._subagents:
            return "No subagents."

        parts = []
        for agent in self._subagents.values():
            status_icon = {
                "pending": "[ ]",
                "running": "[~]",
                "completed": "[x]",
                "failed": "[-]",
            }.get(agent.status, "[ ]")

            parts.append(f"{status_icon} Agent {agent.id}: {agent.task[:50]}...")

        return "\n".join(parts)
