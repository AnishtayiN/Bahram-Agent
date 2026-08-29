"""Trajectory generation for Bahram Agent."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TrajectoryStep:
    """A single step in a trajectory."""

    role: str  # user, assistant, tool
    content: str
    tool_call: Optional[dict] = None
    tool_result: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Trajectory:
    """A complete trajectory of an agent interaction."""

    id: str
    steps: list[TrajectoryStep] = field(default_factory=list)
    model: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


class TrajectoryGenerator:
    """Generate and manage trajectories for training."""

    def __init__(self, output_dir: str = "data/trajectories") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.trajectories: dict[str, Trajectory] = {}

    def start_trajectory(self, trajectory_id: str, model: str = "") -> Trajectory:
        """Start a new trajectory."""
        trajectory = Trajectory(id=trajectory_id, model=model)
        self.trajectories[trajectory_id] = trajectory
        return trajectory

    def add_step(
        self,
        trajectory_id: str,
        role: str,
        content: str,
        tool_call: dict = None,
        tool_result: str = None,
    ) -> None:
        """Add a step to a trajectory."""
        trajectory = self.trajectories.get(trajectory_id)
        if trajectory:
            step = TrajectoryStep(
                role=role,
                content=content,
                tool_call=tool_call,
                tool_result=tool_result,
            )
            trajectory.steps.append(step)

    def end_trajectory(self, trajectory_id: str) -> Optional[Trajectory]:
        """End and save a trajectory."""
        trajectory = self.trajectories.get(trajectory_id)
        if trajectory:
            self._save_trajectory(trajectory)
            return trajectory
        return None

    def _save_trajectory(self, trajectory: Trajectory) -> None:
        """Save trajectory to file."""
        output_file = self.output_dir / f"trajectory_{trajectory.id}.json"

        data = {
            "id": trajectory.id,
            "model": trajectory.model,
            "created_at": trajectory.created_at,
            "steps": [
                {
                    "role": step.role,
                    "content": step.content,
                    "tool_call": step.tool_call,
                    "tool_result": step.tool_result,
                    "timestamp": step.timestamp,
                }
                for step in trajectory.steps
            ],
            "metadata": trajectory.metadata,
        }

        with open(output_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved trajectory: {trajectory.id}")

    def export_sharegpt(self, trajectory_id: str) -> Optional[dict]:
        """Export trajectory in ShareGPT format."""
        trajectory = self.trajectories.get(trajectory_id)
        if not trajectory:
            return None

        conversations = []
        for step in trajectory.steps:
            if step.role == "user":
                conversations.append({"from": "human", "value": step.content})
            elif step.role == "assistant":
                conversations.append({"from": "gpt", "value": step.content})

        return {
            "conversations": conversations,
            "metadata": {
                "model": trajectory.model,
                "trajectory_id": trajectory.id,
            },
        }

    def load_trajectory(self, trajectory_id: str) -> Optional[Trajectory]:
        """Load a trajectory from file."""
        output_file = self.output_dir / f"trajectory_{trajectory_id}.json"
        if not output_file.exists():
            return None

        try:
            with open(output_file) as f:
                data = json.load(f)

            trajectory = Trajectory(
                id=data["id"],
                model=data.get("model", ""),
                created_at=data.get("created_at", ""),
                metadata=data.get("metadata", {}),
            )

            for step_data in data.get("steps", []):
                step = TrajectoryStep(
                    role=step_data["role"],
                    content=step_data["content"],
                    tool_call=step_data.get("tool_call"),
                    tool_result=step_data.get("tool_result"),
                    timestamp=step_data.get("timestamp", ""),
                )
                trajectory.steps.append(step)

            return trajectory

        except Exception as e:
            logger.error(f"Failed to load trajectory: {e}")
            return None

    def list_trajectories(self) -> list[str]:
        """List all trajectory IDs."""
        return list(self.trajectories.keys())

    def compress_trajectory(self, trajectory_id: str) -> Optional[str]:
        """Compress a trajectory for storage."""
        trajectory = self.trajectories.get(trajectory_id)
        if not trajectory:
            return None

        # Create compressed version
        compressed = {
            "id": trajectory.id,
            "model": trajectory.model,
            "num_steps": len(trajectory.steps),
            "summary": f"Trajectory with {len(trajectory.steps)} steps",
        }

        return json.dumps(compressed)
