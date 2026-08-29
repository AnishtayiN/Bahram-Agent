"""Performance monitoring tool for Bahram Agent."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Metric:
    """A performance metric."""

    name: str
    value: float
    timestamp: float
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    """A performance alert."""

    name: str
    condition: str
    threshold: float
    current_value: float = 0.0
    triggered: bool = False


class PerformanceMonitor:
    """Monitor performance metrics."""

    def __init__(self) -> None:
        self._metrics: dict[str, list[Metric]] = {}
        self._alerts: list[Alert] = []
        self._counters: dict[str, int] = {}
        self._timers: dict[str, float] = {}

    def record(self, name: str, value: float, tags: dict[str, str] = None) -> None:
        """Record a metric."""
        if name not in self._metrics:
            self._metrics[name] = []

        self._metrics[name].append(Metric(
            name=name,
            value=value,
            timestamp=time.time(),
            tags=tags or {},
        ))

        # Check alerts
        self._check_alerts(name, value)

    def increment(self, name: str, value: int = 1) -> None:
        """Increment a counter."""
        self._counters[name] = self._counters.get(name, 0) + value
        self.record(name, self._counters[name])

    def start_timer(self, name: str) -> None:
        """Start a timer."""
        self._timers[name] = time.time()

    def stop_timer(self, name: str) -> float:
        """Stop a timer and record duration."""
        if name in self._timers:
            duration = time.time() - self._timers[name]
            del self._timers[name]
            self.record(f"{name}_duration", duration)
            return duration
        return 0.0

    def add_alert(self, name: str, condition: str, threshold: float) -> None:
        """Add an alert."""
        self._alerts.append(Alert(
            name=name,
            condition=condition,
            threshold=threshold,
        ))

    def _check_alerts(self, name: str, value: float) -> None:
        """Check alerts."""
        for alert in self._alerts:
            if alert.name == name:
                alert.current_value = value
                if alert.condition == "greater" and value > alert.threshold:
                    if not alert.triggered:
                        alert.triggered = True
                        logger.warning(f"Alert triggered: {name} = {value} > {alert.threshold}")
                elif alert.condition == "less" and value < alert.threshold:
                    if not alert.triggered:
                        alert.triggered = True
                        logger.warning(f"Alert triggered: {name} = {value} < {alert.threshold}")

    def get_metric(self, name: str, limit: int = 100) -> list[dict]:
        """Get metric history."""
        metrics = self._metrics.get(name, [])[-limit:]
        return [
            {"value": m.value, "timestamp": m.timestamp, "tags": m.tags}
            for m in metrics
        ]

    def get_counter(self, name: str) -> int:
        """Get counter value."""
        return self._counters.get(name, 0)

    def get_summary(self) -> dict[str, Any]:
        """Get performance summary."""
        summary = {}
        for name, metrics in self._metrics.items():
            if metrics:
                values = [m.value for m in metrics]
                summary[name] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                }
        return summary

    def get_alerts(self) -> list[dict]:
        """Get triggered alerts."""
        return [
            {"name": a.name, "condition": a.condition, "threshold": a.threshold, "current": a.current_value}
            for a in self._alerts
            if a.triggered
        ]
