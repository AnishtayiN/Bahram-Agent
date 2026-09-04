from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

@dataclass
class Metric:

    name: str
    value: float
    timestamp: float
    tags: dict[str, str] = field(default_factory=dict)

@dataclass
class Alert:

    name: str
    condition: str
    threshold: float
    current_value: float = 0.0
    triggered: bool = False

class PerformanceMonitor:

    def __init__(self) -> None:
        self._metrics: dict[str, list[Metric]] = {}
        self._alerts: list[Alert] = []
        self._counters: dict[str, int] = {}
        self._timers: dict[str, float] = {}

    def record(self, name: str, value: float, tags: dict[str, str] = None) -> None:
        if name not in self._metrics:
            self._metrics[name] = []

        self._metrics[name].append(Metric(
            name=name,
            value=value,
            timestamp=time.time(),
            tags=tags or {},
        ))

        self._check_alerts(name, value)

    def increment(self, name: str, value: int = 1) -> None:
        self._counters[name] = self._counters.get(name, 0) + value
        self.record(name, self._counters[name])

    def start_timer(self, name: str) -> None:
        self._timers[name] = time.time()

    def stop_timer(self, name: str) -> float:
        if name in self._timers:
            duration = time.time() - self._timers[name]
            del self._timers[name]
            self.record(f"{name}_duration", duration)
            return duration
        return 0.0

    def add_alert(self, name: str, condition: str, threshold: float) -> None:
        self._alerts.append(Alert(
            name=name,
            condition=condition,
            threshold=threshold,
        ))

    def _check_alerts(self, name: str, value: float) -> None:
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
        metrics = self._metrics.get(name, [])[-limit:]
        return [
            {"value": m.value, "timestamp": m.timestamp, "tags": m.tags}
            for m in metrics
        ]

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def get_summary(self) -> dict[str, Any]:
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
        return [
            {"name": a.name, "condition": a.condition, "threshold": a.threshold, "current": a.current_value}
            for a in self._alerts
            if a.triggered
        ]
