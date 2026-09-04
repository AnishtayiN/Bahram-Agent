from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bahram.autonomy.plan import Plan, PlanStatus, StepStatus

logger = logging.getLogger(__name__)


@dataclass
class CheckpointData:
    run_id: str
    plan_id: str
    plan_state: dict[str, Any]
    completed_steps: list[str]
    context_summary: str
    job_state: dict[str, Any] | None = None
    tool_state: dict[str, Any] = field(default_factory=dict)
    retry_info: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class RecoveryManager:
    def __init__(self, data_dir: str = "data/recovery") -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoints_file = self._data_dir / "recovery_checkpoints.json"
        self._checkpoints: dict[str, CheckpointData] = {}
        self._load()

    def _load(self) -> None:
        if self._checkpoints_file.exists():
            try:
                with open(self._checkpoints_file) as f:
                    data = json.load(f)
                for run_id, cp_data in data.items():
                    self._checkpoints[run_id] = CheckpointData(
                        run_id=cp_data["run_id"],
                        plan_id=cp_data["plan_id"],
                        plan_state=cp_data["plan_state"],
                        completed_steps=cp_data["completed_steps"],
                        context_summary=cp_data["context_summary"],
                        job_state=cp_data.get("job_state"),
                        tool_state=cp_data.get("tool_state", {}),
                        retry_info=cp_data.get("retry_info", {}),
                        timestamp=cp_data.get("timestamp", time.time()),
                    )
            except Exception as e:
                logger.warning(f"Failed to load recovery checkpoints: {e}")

    def _save(self) -> None:
        try:
            data = {}
            for run_id, cp in self._checkpoints.items():
                data[run_id] = {
                    "run_id": cp.run_id,
                    "plan_id": cp.plan_id,
                    "plan_state": cp.plan_state,
                    "completed_steps": cp.completed_steps,
                    "context_summary": cp.context_summary,
                    "job_state": cp.job_state,
                    "tool_state": cp.tool_state,
                    "retry_info": cp.retry_info,
                    "timestamp": cp.timestamp,
                }
            with open(self._checkpoints_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save recovery checkpoints: {e}")

    def checkpoint(
        self,
        run_id: str,
        plan: Plan,
        context_summary: str = "",
        job_state: dict[str, Any] | None = None,
        tool_state: dict[str, Any] | None = None,
    ) -> CheckpointData:
        completed_steps = [s.id for s in plan.get_completed_steps()]

        cp = CheckpointData(
            run_id=run_id,
            plan_id=plan.id,
            plan_state=plan.to_dict(),
            completed_steps=completed_steps,
            context_summary=context_summary,
            job_state=job_state,
            tool_state=tool_state or {},
        )

        self._checkpoints[run_id] = cp
        self._save()

        logger.info(
            f"Checkpointed run {run_id}: {len(completed_steps)}/{len(plan.steps)} steps completed"
        )
        return cp

    def load_checkpoint(self, run_id: str) -> CheckpointData | None:
        return self._checkpoints.get(run_id)

    def list_checkpoints(self) -> list[dict[str, Any]]:
        return [
            {
                "run_id": cp.run_id,
                "plan_id": cp.plan_id,
                "completed_steps": len(cp.completed_steps),
                "total_steps": len(cp.plan_state.get("steps", [])),
                "timestamp": cp.timestamp,
            }
            for cp in self._checkpoints.values()
        ]

    def delete_checkpoint(self, run_id: str) -> bool:
        if run_id in self._checkpoints:
            del self._checkpoints[run_id]
            self._save()
            return True
        return False

    def find_interrupted_runs(self) -> list[CheckpointData]:
        """Find runs that were interrupted (have checkpoints but no completion)."""
        return list(self._checkpoints.values())

    def resume_plan(self, checkpoint: CheckpointData) -> Plan:
        """Reconstruct a plan from checkpoint data, marking completed steps."""
        plan = Plan.from_dict(checkpoint.plan_state)

        for step in plan.steps:
            if step.id in checkpoint.completed_steps:
                step.status = StepStatus.COMPLETED
            elif step.status == StepStatus.RUNNING:
                step.status = StepStatus.PENDING
                step.attempt_count += 1

        plan.status = PlanStatus.EXECUTING
        plan.updated_at = time.time()
        return plan

    def can_safely_resume(self, checkpoint: CheckpointData) -> bool:
        """Determine if a run can be safely resumed."""
        plan_state = checkpoint.plan_state
        status = plan_state.get("status", "")

        if status in (PlanStatus.COMPLETED.value, PlanStatus.CANCELLED.value):
            return False

        if checkpoint.completed_steps:
            return True

        return False

    def cleanup_old(self, max_age_hours: float = 24) -> int:
        cutoff = time.time() - (max_age_hours * 3600)
        to_remove = [run_id for run_id, cp in self._checkpoints.items() if cp.timestamp < cutoff]
        for run_id in to_remove:
            del self._checkpoints[run_id]
        if to_remove:
            self._save()
        return len(to_remove)
