"""
Status.

Public objects: ``redact_secrets``, ``RuntimeStatus``, ``status_report``, ``ComponentHealth``,
    ``doctor_check``.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(?:api[_-]?key|apikey)\s*[:=]\s*[\"']?([A-Za-z0-9_\-\.]{20,})", re.IGNORECASE),
        "API_KEY",
    ),
    (
        re.compile(
            r"(?:token|bot_token|bot_token)\s*[:=]\s*[\"']?([A-Za-z0-9:_\-]{20,})", re.IGNORECASE
        ),
        "TOKEN",
    ),
    (
        re.compile(r"(?:secret|password|passwd)\s*[:=]\s*[\"']?([^\s\"',;]{8,})", re.IGNORECASE),
        "SECRET",
    ),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "OPENAI_KEY"),
    (re.compile(r"AIza[A-Za-z0-9_\-]{20,}"), "GEMINI_KEY"),
    (re.compile(r"xoxb-[A-Za-z0-9\-]+"), "SLACK_TOKEN"),
    (re.compile(r"\d{10,12}:[A-Za-zA-Z0-9_\-]{30,}"), "TELEGRAM_BOT_TOKEN"),
    (re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}"), "AWS_ACCESS_KEY"),
    (re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{30,}"), "GITHUB_TOKEN"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"), "JWT"),
]


def redact_secrets(text: str) -> str:
    """Mask sensitive patterns in text to prevent secret leakage in logs."""
    if not text:
        return text
    result = text
    for pattern, label in _SECRET_PATTERNS:
        result = pattern.sub(f"[REDACTED_{label}]", result)
    for key, value in os.environ.items():
        key_lower = key.lower()
        if any(s in key_lower for s in ("key", "secret", "token", "password", "credential")):
            if value and len(value) >= 6:
                result = result.replace(value, f"[REDACTED_ENV:{key}]")
    return result


@dataclass
class RuntimeStatus:
    """Collects and holds runtime status from engine subsystems."""

    active_runs: int = 0
    active_jobs: int = 0
    active_subagents: int = 0
    provider_health: dict[str, dict[str, Any]] = field(default_factory=dict)
    tool_success_rate: float = 0.0
    budget_usage: dict[str, Any] = field(default_factory=dict)
    circuit_breaker_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    error_counts: dict[str, int] = field(default_factory=dict)
    estimated_cost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """
        Serialise the object to a JSON-serialisable dictionary.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {
            "active_runs": self.active_runs,
            "active_jobs": self.active_jobs,
            "active_subagents": self.active_subagents,
            "provider_health": self.provider_health,
            "tool_success_rate": self.tool_success_rate,
            "budget_usage": self.budget_usage,
            "circuit_breaker_states": self.circuit_breaker_states,
            "error_counts": self.error_counts,
            "estimated_cost": self.estimated_cost,
        }


def _collect_tool_stats(tool_executor: Any) -> dict[str, Any]:
    log: list[dict[str, Any]] = getattr(tool_executor, "_log", [])
    total = len(log)
    if total == 0:
        return {"total": 0, "success": 0, "failure": 0, "rate": 0.0}
    success = sum(1 for e in log if e.get("status") == "success")
    failure = total - success
    return {
        "total": total,
        "success": success,
        "failure": failure,
        "rate": success / total if total > 0 else 0.0,
    }


def _collect_error_counts(event_tracker: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    if event_tracker is None or not hasattr(event_tracker, "_events"):
        return counts
    for event in event_tracker._events:
        et = getattr(event, "event_type", "")
        if "fail" in et or "error" in et or "exceeded" in et:
            counts[et] = counts.get(et, 0) + 1
    return counts


def status_report(
    engine: Any = None,
    job_engine: Any = None,
    subagent_engine: Any = None,
    budget_manager: Any = None,
    event_tracker: Any = None,
) -> dict[str, Any]:
    """Build a status report from live engine subsystems. Returns a plain dict."""
    rs = RuntimeStatus()

    if engine is not None:
        executor = getattr(engine, "_tool_executor", None)
        if executor is not None:
            stats = _collect_tool_stats(executor)
            rs.tool_success_rate = stats["rate"]

        circuit = getattr(engine, "_circuit_breaker", None)
        if circuit is not None and hasattr(circuit, "get_status"):
            rs.circuit_breaker_states = circuit.get_status()

    if job_engine is not None:
        queue = job_engine.get_queue_depth() if hasattr(job_engine, "get_queue_depth") else {}
        running = queue.get("running", 0) + queue.get("starting", 0) + queue.get("retrying", 0)
        rs.active_jobs = running

    if subagent_engine is not None:
        rs.active_subagents = (
            subagent_engine.get_active_count()
            if hasattr(subagent_engine, "get_active_count")
            else 0
        )

    if budget_manager is not None:
        all_usage = (
            budget_manager.get_all_usage() if hasattr(budget_manager, "get_all_usage") else {}
        )
        runs = all_usage.get("runs", {})
        total_cost = sum(r.get("cost_usd", 0.0) for r in runs.values())
        rs.estimated_cost = total_cost
        rs.budget_usage = all_usage

    if event_tracker is not None:
        rs.error_counts = _collect_error_counts(event_tracker)

    return rs.to_dict()


@dataclass
class ComponentHealth:
    """
    Component health.

    Attributes:
        name (str): name of the object.
        healthy (bool): when ``True``, enable healthy.
        message (str): message to process.
    """

    name: str
    healthy: bool
    message: str = ""


def doctor_check(
    engine: Any = None,
    job_engine: Any = None,
    subagent_engine: Any = None,
    budget_manager: Any = None,
) -> list[dict[str, Any]]:
    """Check health of all subsystems. Returns list of component health dicts."""
    components: list[ComponentHealth] = []

    if engine is not None:
        providers = getattr(engine, "providers", {})
        if providers:
            components.append(ComponentHealth("providers", True, f"{len(providers)} registered"))
        else:
            components.append(ComponentHealth("providers", False, "No providers registered"))

        tools = getattr(engine, "tools", {})
        if tools:
            components.append(ComponentHealth("tools", True, f"{len(tools)} registered"))
        else:
            components.append(ComponentHealth("tools", False, "No tools registered"))
    else:
        components.append(ComponentHealth("engine", False, "Engine not provided"))

    if job_engine is not None:
        components.append(ComponentHealth("job_engine", True, "Job engine available"))
    else:
        components.append(ComponentHealth("job_engine", False, "Job engine not provided"))

    if subagent_engine is not None:
        max_conc = getattr(subagent_engine, "_max_concurrent", 5)
        components.append(ComponentHealth("subagent_engine", True, f"max_concurrent={max_conc}"))
    else:
        components.append(ComponentHealth("subagent_engine", False, "Subagent engine not provided"))

    if budget_manager is not None:
        config = budget_manager.config if hasattr(budget_manager, "config") else None
        if config is not None:
            components.append(
                ComponentHealth(
                    "budget_manager",
                    True,
                    f"max_cost=${config.max_cost_usd:.2f}",
                )
            )
        else:
            components.append(ComponentHealth("budget_manager", True, "Available"))
    else:
        components.append(ComponentHealth("budget_manager", False, "Budget manager not provided"))

    return [c.__dict__ for c in components]
