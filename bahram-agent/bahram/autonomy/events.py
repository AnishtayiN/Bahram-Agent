"""
Events.

Public objects: ``Event``, ``EventTracker``.
"""

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
    """
    Event.

    Attributes:
        id (str): id string.
        event_type (str): event type string.
        session_id (str): session identifier.
        run_id (str): run identifier.
        plan_id (str): plan identifier.
        step_id (str): plan-step identifier.
        job_id (str): job identifier.
        tool_call_id (str): tool call id string.
        subagent_id (str): subagent id string.
        data (dict[str, Any]): mapping of data.
        timestamp (float): numeric value for timestamp.
    """

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
        """
        Serialise the object to a JSON-serialisable dictionary.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
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
    """
    Event tracker.
    """

    def __init__(self, data_dir: str | None = "data/events") -> None:
        """Initialise a EventTracker instance.

        Args:
            data_dir (str | None): directory that holds the on-disk state, or
                ``None`` to keep events in memory only. Defaults to
                ``'data/events'``.
        """
        self._data_dir = Path(data_dir) if data_dir else None
        self._events_file = self._data_dir / "events.jsonl" if self._data_dir else None
        if self._data_dir is not None:
            self._data_dir.mkdir(parents=True, exist_ok=True)
        self._events: list[Event] = []
        self._load_events()

    def _append_event(self, event: Event) -> None:
        self._events.append(event)
        if self._events_file is None:
            return
        try:
            with open(self._events_file, "a") as f:
                f.write(json.dumps(event.to_dict(), default=str) + "\n")
        except Exception as e:
            logger.warning(f"Failed to persist event: {e}")

    def _load_events(self) -> None:
        """Load events from JSONL file on startup."""
        if self._events_file is None or not self._events_file.exists():
            return
        try:
            with open(self._events_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    self._events.append(
                        Event(
                            id=data["id"],
                            event_type=data["event_type"],
                            session_id=data.get("session_id", ""),
                            run_id=data.get("run_id", ""),
                            plan_id=data.get("plan_id", ""),
                            step_id=data.get("step_id", ""),
                            job_id=data.get("job_id", ""),
                            tool_call_id=data.get("tool_call_id", ""),
                            subagent_id=data.get("subagent_id", ""),
                            data=data.get("data", {}),
                            timestamp=data.get("timestamp", 0.0),
                        )
                    )
        except Exception as e:
            logger.warning(f"Failed to load events: {e}")

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
        """
        Emit.

        Args:
            event_type (str): event type string.
            session_id (str): session identifier. Defaults to ``''``.
            run_id (str): run identifier. Defaults to ``''``.
            plan_id (str): plan identifier. Defaults to ``''``.
            step_id (str): plan-step identifier. Defaults to ``''``.
            job_id (str): job identifier. Defaults to ``''``.
            tool_call_id (str): tool call id string. Defaults to ``''``.
            subagent_id (str): subagent id string. Defaults to ``''``.
            data (dict[str, Any] | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
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

    def emit_plan_created(
        self, session_id: str, run_id: str, plan_id: str, data: dict | None = None
    ) -> Event:
        """
        Emit a ``plan created`` event.

        Args:
            session_id (str): session identifier.
            run_id (str): run identifier.
            plan_id (str): plan identifier.
            data (dict | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
        return self.emit("plan_created", session_id, run_id, plan_id=plan_id, data=data or {})

    def emit_plan_updated(
        self, session_id: str, run_id: str, plan_id: str, data: dict | None = None
    ) -> Event:
        """
        Emit a ``plan updated`` event.

        Args:
            session_id (str): session identifier.
            run_id (str): run identifier.
            plan_id (str): plan identifier.
            data (dict | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
        return self.emit("plan_updated", session_id, run_id, plan_id=plan_id, data=data or {})

    def emit_step_started(
        self, session_id: str, run_id: str, plan_id: str, step_id: str, data: dict | None = None
    ) -> Event:
        """
        Emit a ``step started`` event.

        Args:
            session_id (str): session identifier.
            run_id (str): run identifier.
            plan_id (str): plan identifier.
            step_id (str): plan-step identifier.
            data (dict | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
        return self.emit(
            "step_started", session_id, run_id, plan_id=plan_id, step_id=step_id, data=data or {}
        )

    def emit_step_completed(
        self, session_id: str, run_id: str, plan_id: str, step_id: str, data: dict | None = None
    ) -> Event:
        """
        Emit a ``step completed`` event.

        Args:
            session_id (str): session identifier.
            run_id (str): run identifier.
            plan_id (str): plan identifier.
            step_id (str): plan-step identifier.
            data (dict | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
        return self.emit(
            "step_completed", session_id, run_id, plan_id=plan_id, step_id=step_id, data=data or {}
        )

    def emit_step_failed(
        self, session_id: str, run_id: str, plan_id: str, step_id: str, data: dict | None = None
    ) -> Event:
        """
        Emit a ``step failed`` event.

        Args:
            session_id (str): session identifier.
            run_id (str): run identifier.
            plan_id (str): plan identifier.
            step_id (str): plan-step identifier.
            data (dict | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
        return self.emit(
            "step_failed", session_id, run_id, plan_id=plan_id, step_id=step_id, data=data or {}
        )

    def emit_replanned(
        self, session_id: str, run_id: str, plan_id: str, data: dict | None = None
    ) -> Event:
        """
        Emit a ``replanned`` event.

        Args:
            session_id (str): session identifier.
            run_id (str): run identifier.
            plan_id (str): plan identifier.
            data (dict | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
        return self.emit("replanned", session_id, run_id, plan_id=plan_id, data=data or {})

    def emit_subagent_spawned(
        self, session_id: str, run_id: str, subagent_id: str, data: dict | None = None
    ) -> Event:
        """
        Emit a ``subagent spawned`` event.

        Args:
            session_id (str): session identifier.
            run_id (str): run identifier.
            subagent_id (str): subagent id string.
            data (dict | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
        return self.emit(
            "subagent_spawned", session_id, run_id, subagent_id=subagent_id, data=data or {}
        )

    def emit_subagent_completed(
        self, session_id: str, run_id: str, subagent_id: str, data: dict | None = None
    ) -> Event:
        """
        Emit a ``subagent completed`` event.

        Args:
            session_id (str): session identifier.
            run_id (str): run identifier.
            subagent_id (str): subagent id string.
            data (dict | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
        return self.emit(
            "subagent_completed", session_id, run_id, subagent_id=subagent_id, data=data or {}
        )

    def emit_job_started(
        self, session_id: str, run_id: str, job_id: str, data: dict | None = None
    ) -> Event:
        """
        Emit a ``job started`` event.

        Args:
            session_id (str): session identifier.
            run_id (str): run identifier.
            job_id (str): job identifier.
            data (dict | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
        return self.emit("job_started", session_id, run_id, job_id=job_id, data=data or {})

    def emit_job_checkpointed(
        self, session_id: str, run_id: str, job_id: str, data: dict | None = None
    ) -> Event:
        """
        Emit a ``job checkpointed`` event.

        Args:
            session_id (str): session identifier.
            run_id (str): run identifier.
            job_id (str): job identifier.
            data (dict | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
        return self.emit("job_checkpointed", session_id, run_id, job_id=job_id, data=data or {})

    def emit_job_resumed(
        self, session_id: str, run_id: str, job_id: str, data: dict | None = None
    ) -> Event:
        """
        Emit a ``job resumed`` event.

        Args:
            session_id (str): session identifier.
            run_id (str): run identifier.
            job_id (str): job identifier.
            data (dict | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
        return self.emit("job_resumed", session_id, run_id, job_id=job_id, data=data or {})

    def emit_provider_fallback(
        self, session_id: str, run_id: str, data: dict | None = None
    ) -> Event:
        """
        Emit a ``provider fallback`` event.

        Args:
            session_id (str): session identifier.
            run_id (str): run identifier.
            data (dict | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
        return self.emit("provider_fallback", session_id, run_id, data=data or {})

    def emit_memory_retrieved(
        self, session_id: str, run_id: str, data: dict | None = None
    ) -> Event:
        """
        Emit a ``memory retrieved`` event.

        Args:
            session_id (str): session identifier.
            run_id (str): run identifier.
            data (dict | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
        return self.emit("memory_retrieved", session_id, run_id, data=data or {})

    def emit_skill_selected(self, session_id: str, run_id: str, data: dict | None = None) -> Event:
        """
        Emit a ``skill selected`` event.

        Args:
            session_id (str): session identifier.
            run_id (str): run identifier.
            data (dict | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
        return self.emit("skill_selected", session_id, run_id, data=data or {})

    def emit_skill_promoted(self, session_id: str, run_id: str, data: dict | None = None) -> Event:
        """
        Emit a ``skill promoted`` event.

        Args:
            session_id (str): session identifier.
            run_id (str): run identifier.
            data (dict | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
        return self.emit("skill_promoted", session_id, run_id, data=data or {})

    def emit_budget_warning(self, session_id: str, run_id: str, data: dict | None = None) -> Event:
        """
        Emit a ``budget warning`` event.

        Args:
            session_id (str): session identifier.
            run_id (str): run identifier.
            data (dict | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
        return self.emit("budget_warning", session_id, run_id, data=data or {})

    def emit_budget_exceeded(self, session_id: str, run_id: str, data: dict | None = None) -> Event:
        """
        Emit a ``budget exceeded`` event.

        Args:
            session_id (str): session identifier.
            run_id (str): run identifier.
            data (dict | None): mapping of data. Defaults to ``None``.

        Returns:
            Event: the resulting Event.
        """
        return self.emit("budget_exceeded", session_id, run_id, data=data or {})

    def query_events(
        self,
        event_type: str | None = None,
        session_id: str | None = None,
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """
        Query events.

        Args:
            event_type (str | None): event type string. Defaults to ``None``.
            session_id (str | None): session identifier. Defaults to ``None``.
            run_id (str | None): run identifier. Defaults to ``None``.
            limit (int): maximum number of items to return. Defaults to ``100``.

        Returns:
            list[Event]: a sequence of Event entries (empty when there is nothing to report).
        """
        results = self._events
        if event_type:
            results = [e for e in results if e.event_type == event_type]
        if session_id:
            results = [e for e in results if e.session_id == session_id]
        if run_id:
            results = [e for e in results if e.run_id == run_id]
        return results[-limit:]

    def get_trace(self, run_id: str) -> list[Event]:
        """
        Return the trace.

        Args:
            run_id (str): run identifier.

        Returns:
            list[Event]: a sequence of Event entries (empty when there is nothing to report).
        """
        return sorted(
            [e for e in self._events if e.run_id == run_id],
            key=lambda e: e.timestamp,
        )
