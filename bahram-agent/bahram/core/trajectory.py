"""Trajectory generation for Bahram Agent."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TrajectoryStep:
    """A step in a trajectory."""

    step_id: int
    action: str
    input: str
    output: str
    timestamp: float
    duration: float = 0.0


@dataclass
class Trajectory:
    """A complete trajectory."""

    id: str
    name: str
    steps: list[TrajectoryStep] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    status: str = "running"


class TrajectoryGenerator:
    """Generate and track trajectories."""

    def __init__(self, data_dir: str = "data/trajectories") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._trajectories: dict[str, Trajectory] = {}
        self._current: Optional[Trajectory] = None

    def start(self, name: str) -> Trajectory:
        """Start a new trajectory."""
        import hashlib
        traj_id = hashlib.md5(f"{name}{time.time()}".encode()).hexdigest()[:12]

        trajectory = Trajectory(
            id=traj_id,
            name=name,
            start_time=time.time(),
        )
        self._trajectories[traj_id] = trajectory
        self._current = trajectory
        return trajectory

    def add_step(self, action: str, input_text: str, output: str) -> None:
        """Add a step to current trajectory."""
        if not self._current:
            return

        step = TrajectoryStep(
            step_id=len(self._current.steps),
            action=action,
            input=input_text,
            output=output,
            timestamp=time.time(),
        )
        self._current.steps.append(step)

    def finish(self, status: str = "completed") -> Optional[Trajectory]:
        """Finish current trajectory."""
        if not self._current:
            return None

        self._current.end_time = time.time()
        self._current.status = status
        result = self._current
        self._current = None
        self._save(result)
        return result

    def _save(self, trajectory: Trajectory) -> None:
        """Save trajectory to disk."""
        traj_file = self.data_dir / f"{trajectory.id}.json"
        data = {
            "id": trajectory.id,
            "name": trajectory.name,
            "start_time": trajectory.start_time,
            "end_time": trajectory.end_time,
            "status": trajectory.status,
            "steps": [
                {
                    "step_id": s.step_id,
                    "action": s.action,
                    "input": s.input[:500],
                    "output": s.output[:500],
                    "timestamp": s.timestamp,
                    "duration": s.duration,
                }
                for s in trajectory.steps
            ],
        }
        with open(traj_file, "w") as f:
            json.dump(data, f, indent=2)

    def get_trajectory(self, traj_id: str) -> Optional[Trajectory]:
        """Get a trajectory by ID."""
        return self._trajectories.get(traj_id)

    def list_trajectories(self) -> list[dict]:
        """List all trajectories."""
        return [
            {
                "id": t.id,
                "name": t.name,
                "status": t.status,
                "steps": len(t.steps),
                "duration": t.end_time - t.start_time if t.end_time else 0,
            }
            for t in self._trajectories.values()
        ]

    def format_trajectory(self, traj_id: str) -> str:
        """Format a trajectory as text."""
        traj = self.get_trajectory(traj_id)
        if not traj:
            return "Trajectory not found"

        lines = [
            f"Trajectory: {traj.name}",
            f"Status: {traj.status}",
            f"Duration: {traj.end_time - traj.start_time:.1f}s",
            "",
            "Steps:",
        ]

        for step in traj.steps:
            lines.append(f"  {step.step_id + 1}. {step.action}")
            lines.append(f"     Input: {step.input[:100]}...")
            lines.append(f"     Output: {step.output[:100]}...")
            lines.append("")

        return "\n".join(lines)
