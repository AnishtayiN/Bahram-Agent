"""Task tool for spawning subagents."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from bahram.tools.base import BaseTool

logger = logging.getLogger(__name__)


class TaskTool(BaseTool):
    """Tool for spawning isolated subagents."""

    @property
    def name(self) -> str:
        return "task"

    @property
    def description(self) -> str:
        return """Spawn an isolated subagent to handle a specific task.
Subagents have their own context and can work independently.
Useful for parallel workstreams or complex multi-step tasks."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Brief description of the task",
                },
                "prompt": {
                    "type": "string",
                    "description": "Detailed prompt for the subagent",
                },
                "agent_type": {
                    "type": "string",
                    "description": "Type of agent to spawn (default: general)",
                },
            },
            "required": ["description", "prompt"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """Spawn a subagent."""
        description = kwargs.get("description", "")
        prompt = kwargs.get("prompt", "")
        agent_type = kwargs.get("agent_type", "general")

        if not description or not prompt:
            return "Error: description and prompt are required"

        task_id = str(uuid.uuid4())[:8]
        logger.info(f"Spawning subagent {task_id}: {description}")

        # In a real implementation, this would spawn an actual subagent
        # For now, we'll simulate it
        try:
            # Simulate subagent execution
            await asyncio.sleep(0.1)  # Simulate work

            result = f"""Subagent {task_id} completed:
Task: {description}
Type: {agent_type}
Status: Success

The subagent has completed its task. In a full implementation, this would
return the actual results from the subagent's work."""

            return result

        except Exception as e:
            return f"Error spawning subagent: {e}"
