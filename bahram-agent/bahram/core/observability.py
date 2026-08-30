from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ObservabilityEvent:
    event_id: str
    event_type: str
    session_id: str
    run_id: str
    plan_id: str = ""
    step_id: str = ""
    tool_call_id: str = ""
    subagent_id: str = ""
    job_id: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    correlation_id: str = ""


class Observability:
    def __init__(self, data_dir: str = "data/observability") -> None:
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._events: list[ObservabilityEvent] = []
        self._event_file = os.path.join(data_dir, "events.jsonl")

    def emit(self, event_type: str, session_id: str = "", run_id: str = "",
             correlation_id: str = "", **data: Any) -> ObservabilityEvent:
        event = ObservabilityEvent(
            event_id=str(uuid.uuid4())[:12],
            event_type=event_type,
            session_id=session_id,
            run_id=run_id,
            data=data,
            correlation_id=correlation_id,
        )
        self._events.append(event)
        self._persist(event)
        return event

    def _persist(self, event: ObservabilityEvent) -> None:
        try:
            with open(self._event_file, 'a') as f:
                f.write(json.dumps({
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "session_id": event.session_id,
                    "run_id": event.run_id,
                    "data": event.data,
                    "timestamp": event.timestamp,
                    "correlation_id": event.correlation_id,
                }) + "\n")
        except Exception as e:
            logger.warning(f"Failed to persist observability event: {e}")

    def emit_run_created(self, session_id: str, run_id: str, **data: Any) -> ObservabilityEvent:
        return self.emit("run_created", session_id, run_id, **data)

    def emit_session_loaded(self, session_id: str, **data: Any) -> ObservabilityEvent:
        return self.emit("session_loaded", session_id=session_id, **data)

    def emit_memory_loaded(self, session_id: str, run_id: str, **data: Any) -> ObservabilityEvent:
        return self.emit("memory_loaded", session_id, run_id, **data)

    def emit_context_built(self, session_id: str, run_id: str, **data: Any) -> ObservabilityEvent:
        return self.emit("context_built", session_id, run_id, **data)

    def emit_plan_created(self, session_id: str, run_id: str, plan_id: str = "", **data: Any) -> ObservabilityEvent:
        e = self.emit("plan_created", session_id, run_id, **data)
        e.plan_id = plan_id
        return e

    def emit_step_started(self, session_id: str, run_id: str, step_id: str = "", **data: Any) -> ObservabilityEvent:
        e = self.emit("step_started", session_id, run_id, **data)
        e.step_id = step_id
        return e

    def emit_step_completed(self, session_id: str, run_id: str, step_id: str = "", **data: Any) -> ObservabilityEvent:
        e = self.emit("step_completed", session_id, run_id, **data)
        e.step_id = step_id
        return e

    def emit_step_failed(self, session_id: str, run_id: str, step_id: str = "", **data: Any) -> ObservabilityEvent:
        e = self.emit("step_failed", session_id, run_id, **data)
        e.step_id = step_id
        return e

    def emit_tool_selected(self, session_id: str, run_id: str, tool_name: str = "", **data: Any) -> ObservabilityEvent:
        return self.emit("tool_selected", session_id, run_id, tool_name=tool_name, **data)

    def emit_tool_started(self, session_id: str, run_id: str, tool_call_id: str = "", **data: Any) -> ObservabilityEvent:
        e = self.emit("tool_started", session_id, run_id, **data)
        e.tool_call_id = tool_call_id
        return e

    def emit_tool_completed(self, session_id: str, run_id: str, tool_call_id: str = "", **data: Any) -> ObservabilityEvent:
        e = self.emit("tool_completed", session_id, run_id, **data)
        e.tool_call_id = tool_call_id
        return e

    def emit_tool_failed(self, session_id: str, run_id: str, tool_call_id: str = "", **data: Any) -> ObservabilityEvent:
        e = self.emit("tool_failed", session_id, run_id, **data)
        e.tool_call_id = tool_call_id
        return e

    def emit_replanned(self, session_id: str, run_id: str, **data: Any) -> ObservabilityEvent:
        return self.emit("replanned", session_id, run_id, **data)

    def emit_subagent_spawned(self, session_id: str, run_id: str, subagent_id: str = "", **data: Any) -> ObservabilityEvent:
        e = self.emit("subagent_spawned", session_id, run_id, **data)
        e.subagent_id = subagent_id
        return e

    def emit_subagent_completed(self, session_id: str, run_id: str, subagent_id: str = "", **data: Any) -> ObservabilityEvent:
        e = self.emit("subagent_completed", session_id, run_id, **data)
        e.subagent_id = subagent_id
        return e

    def emit_provider_failed(self, session_id: str, run_id: str, **data: Any) -> ObservabilityEvent:
        return self.emit("provider_failed", session_id, run_id, **data)

    def emit_provider_fallback(self, session_id: str, run_id: str, **data: Any) -> ObservabilityEvent:
        return self.emit("provider_fallback", session_id, run_id, **data)

    def emit_circuit_opened(self, session_id: str, run_id: str, **data: Any) -> ObservabilityEvent:
        return self.emit("circuit_opened", session_id, run_id, **data)

    def emit_circuit_closed(self, session_id: str, run_id: str, **data: Any) -> ObservabilityEvent:
        return self.emit("circuit_closed", session_id, run_id, **data)

    def emit_budget_warning(self, session_id: str, run_id: str, **data: Any) -> ObservabilityEvent:
        return self.emit("budget_warning", session_id, run_id, **data)

    def emit_budget_exceeded(self, session_id: str, run_id: str, **data: Any) -> ObservabilityEvent:
        return self.emit("budget_exceeded", session_id, run_id, **data)

    def emit_context_compressed(self, session_id: str, run_id: str, **data: Any) -> ObservabilityEvent:
        return self.emit("context_compressed", session_id, run_id, **data)

    def emit_lesson_created(self, session_id: str, run_id: str, **data: Any) -> ObservabilityEvent:
        return self.emit("lesson_created", session_id, run_id, **data)

    def emit_skill_promoted(self, session_id: str, run_id: str, **data: Any) -> ObservabilityEvent:
        return self.emit("skill_promoted", session_id, run_id, **data)

    def emit_run_completed(self, session_id: str, run_id: str, **data: Any) -> ObservabilityEvent:
        return self.emit("run_completed", session_id, run_id, **data)

    def emit_approval_requested(self, session_id: str, run_id: str, **data: Any) -> ObservabilityEvent:
        return self.emit("approval_requested", session_id, run_id, **data)

    def emit_approval_granted(self, session_id: str, run_id: str, **data: Any) -> ObservabilityEvent:
        return self.emit("approval_granted", session_id, run_id, **data)

    def query_events(self, session_id: str = "", run_id: str = "",
                     event_type: str = "", limit: int = 100) -> list[ObservabilityEvent]:
        results = self._events
        if session_id:
            results = [e for e in results if e.session_id == session_id]
        if run_id:
            results = [e for e in results if e.run_id == run_id]
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        return results[-limit:]

    def get_event_types(self) -> list[str]:
        return sorted(set(e.event_type for e in self._events))
