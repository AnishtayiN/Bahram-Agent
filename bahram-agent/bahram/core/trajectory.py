"""
Trajectory.

Public objects: ``TrajectoryStep``, ``Trajectory``, ``TrajectoryGenerator``.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TrajectoryStep:
    """
    Trajectory step.

    Attributes:
        step_id (int): plan-step identifier.
        action (str): action string.
        input (str): input string.
        output (str): output string.
        timestamp (float): numeric value for timestamp.
        duration (float): numeric value for duration.
    """

    step_id: int
    action: str
    input: str
    output: str
    timestamp: float
    duration: float = 0.0


@dataclass
class Trajectory:
    """
    Trajectory.

    Attributes:
        id (str): id string.
        name (str): name of the object.
        steps (list[TrajectoryStep]): collection of steps.
        start_time (float): numeric value for start time.
        end_time (float): numeric value for end time.
        status (str): status string.
    """

    id: str
    name: str
    steps: list[TrajectoryStep] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    status: str = "running"


class TrajectoryGenerator:
    """
    Trajectory generator.
    """

    def __init__(self, data_dir: str = "data/trajectories") -> None:
        """
        Initialise a TrajectoryGenerator instance.

        Args:
            data_dir (str): directory that holds the on-disk state. Defaults to
                ``'data/trajectories'``.
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._trajectories: dict[str, Trajectory] = {}
        self._current: Trajectory | None = None

    def start(self, name: str) -> Trajectory:
        """
        Start the component and acquire any resources it needs.

        Args:
            name (str): name of the object.

        Returns:
            Trajectory: the resulting Trajectory.
        """
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
        """
        Add step.

        Args:
            action (str): action string.
            input_text (str): input text string.
            output (str): output string.
        """
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

    def finish(self, status: str = "completed") -> Trajectory | None:
        """
        Finish.

        Args:
            status (str): status string. Defaults to ``'completed'``.

        Returns:
            Trajectory | None: the resulting object, or ``None`` when it is not available.
        """
        if not self._current:
            return None

        self._current.end_time = time.time()
        self._current.status = status
        result = self._current
        self._current = None
        self._save(result)
        return result

    def _save(self, trajectory: Trajectory) -> None:
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

    def get_trajectory(self, traj_id: str) -> Trajectory | None:
        """
        Return the trajectory.

        Args:
            traj_id (str): traj id string.

        Returns:
            Trajectory | None: the resulting object, or ``None`` when it is not available.
        """
        return self._trajectories.get(traj_id)

    def list_trajectories(self) -> list[dict]:
        """
        List trajectories.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
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
        """
        Format trajectory.

        Args:
            traj_id (str): traj id string.

        Returns:
            str: the rendered string.
        """
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
