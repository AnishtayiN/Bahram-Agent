from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Event:
    id: str
    event_type: str
    session_id: str
    run_id: str
    plan_id: str = ""
    step_id: str = ""
    job_id: str = ""
    tool_call_id: str = ""
    subagent_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "session_id": self.session_id,
            "run_id": self.run_id,
            "plan_id": self.plan_id,
            "step_id": self.step_id,
            "job_id": self.job_id,
            "tool_call_id": self.tool_call_id,
            "subagent_id": self.subagent_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class EventTracker:
    def __init__(self, data_dir: str = "data/events") -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._events_file = self._data_dir / "events.jsonl"
        self._events: list[Event] = []

    def _append_event(self, event: Event) -> None:
        self._events.append(event)
        try:
            with open(self._events_file, "a") as f:
                f.write(json.dumps(event.to_dict(), default=str) + "\n")
        except Exception as e:
            logger.warning(f"Failed to persist event: {e}")

    def emit(
        self,
        event_type: str,
        session_id: str = "",
        run_id: str = "",
        plan_id: str = "",
        step_id: str = "",
        job_id: str = "",
        tool_call_id: str = "",
        subagent_id: str = "",
        data: dict[str, Any] | None = None,
    ) -> Event:
        event = Event(
            id=f"evt_{uuid.uuid4().hex[:8]}",
            event_type=event_type,
            session_id=session_id,
            run_id=run_id,
            plan_id=plan_id,
            step_id=step_id,
            job_id=job_id,
            tool_call_id=tool_call_id,
            subagent_id=subagent_id,
            data=data or {},
        )
        self._append_event(event)
        return event

    def emit_plan_created(self, session_id: str, run_id: str, plan_id: str, data: dict | None = None) -> Event:
        return self.emit("plan_created", session_id, run_id, plan_id=plan_id, data=data or {})

    def emit_plan_updated(self, session_id: str, run_id: str, plan_id: str, data: dict | None = None) -> Event:
        return self.emit("plan_updated", session_id, run_id, plan_id=plan_id, data=data or {})

    def emit_step_started(self, session_id: str, run_id: str, plan_id: str, step_id: str, data: dict | None = None) -> Event:
        return self.emit("step_started", session_id, run_id, plan_id=plan_id, step_id=step_id, data=data or {})

    def emit_step_completed(self, session_id: str, run_id: str, plan_id: str, step_id: str, data: dict | None = None) -> Event:
        return self.emit("step_completed", session_id, run_id, plan_id=plan_id, step_id=step_id, data=data or {})

    def emit_step_failed(self, session_id: str, run_id: str, plan_id: str, step_id: str, data: dict | None = None) -> Event:
        return self.emit("step_failed", session_id, run_id, plan_id=plan_id, step_id=step_id, data=data or {})

    def emit_replanned(self, session_id: str, run_id: str, plan_id: str, data: dict | None = None) -> Event:
        return self.emit("replanned", session_id, run_id, plan_id=plan_id, data=data or {})

    def emit_subagent_spawned(self, session_id: str, run_id: str, subagent_id: str, data: dict | None = None) -> Event:
        return self.emit("subagent_spawned", session_id, run_id, subagent_id=subagent_id, data=data or {})

    def emit_subagent_completed(self, session_id: str, run_id: str, subagent_id: str, data: dict | None = None) -> Event:
        return self.emit("subagent_completed", session_id, run_id, subagent_id=subagent_id, data=data or {})

    def emit_job_started(self, session_id: str, run_id: str, job_id: str, data: dict | None = None) -> Event:
        return self.emit("job_started", session_id, run_id, job_id=job_id, data=data or {})

    def emit_job_checkpointed(self, session_id: str, run_id: str, job_id: str, data: dict | None = None) -> Event:
        return self.emit("job_checkpointed", session_id, run_id, job_id=job_id, data=data or {})

    def emit_job_resumed(self, session_id: str, run_id: str, job_id: str, data: dict | None = None) -> Event:
        return self.emit("job_resumed", session_id, run_id, job_id=job_id, data=data or {})

    def emit_provider_fallback(self, session_id: str, run_id: str, data: dict | None = None) -> Event:
        return self.emit("provider_fallback", session_id, run_id, data=data or {})

    def emit_memory_retrieved(self, session_id: str, run_id: str, data: dict | None = None) -> Event:
        return self.emit("memory_retrieved", session_id, run_id, data=data or {})

    def emit_skill_selected(self, session_id: str, run_id: str, data: dict | None = None) -> Event:
        return self.emit("skill_selected", session_id, run_id, data=data or {})

    def emit_skill_promoted(self, session_id: str, run_id: str, data: dict | None = None) -> Event:
        return self.emit("skill_promoted", session_id, run_id, data=data or {})

    def emit_budget_warning(self, session_id: str, run_id: str, data: dict | None = None) -> Event:
        return self.emit("budget_warning", session_id, run_id, data=data or {})

    def emit_budget_exceeded(self, session_id: str, run_id: str, data: dict | None = None) -> Event:
        return self.emit("budget_exceeded", session_id, run_id, data=data or {})

    def query_events(
        self,
        event_type: str | None = None,
        session_id: str | None = None,
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        results = self._events
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if session_id:
            results = [e for e in results if e.session_id == session_id]
        if run_id:
            results = [e for e in results if e.run_id == run_id]
        return results[-limit:]

    def get_trace(self, run_id: str) -> list[Event]:
        return sorted(
            [e for e in self._events if e.run_id == run_id],
            key=lambda e: e.timestamp,
        )
