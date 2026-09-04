"""
Monitoring.

Public objects: ``Metric``, ``Alert``, ``PerformanceMonitor``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Metric:
    """
    Metric.

    Attributes:
        name (str): name of the object.
        value (float): numeric value for value.
        timestamp (float): numeric value for timestamp.
        tags (dict[str, str]): mapping of tags.
    """

    name: str
    value: float
    timestamp: float
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    """
    Alert.

    Attributes:
        name (str): name of the object.
        condition (str): condition string.
        threshold (float): numeric value for threshold.
        current_value (float): numeric value for current value.
        triggered (bool): when ``True``, enable triggered.
    """

    name: str
    condition: str
    threshold: float
    current_value: float = 0.0
    triggered: bool = False


class PerformanceMonitor:
    """
    Performance monitor.
    """

    def __init__(self) -> None:
        """
        Initialise a PerformanceMonitor instance.
        """
        self._metrics: dict[str, list[Metric]] = {}
        self._alerts: list[Alert] = []
        self._counters: dict[str, int] = {}
        self._timers: dict[str, float] = {}

    def record(self, name: str, value: float, tags: dict[str, str] = None) -> None:
        """
        Record.

        Args:
            name (str): name of the object.
            value (float): numeric value for value.
            tags (dict[str, str]): mapping of tags. Defaults to ``None``.
        """
        if name not in self._metrics:
            self._metrics[name] = []

        self._metrics[name].append(
            Metric(
                name=name,
                value=value,
                timestamp=time.time(),
                tags=tags or {},
            )
        )

        self._check_alerts(name, value)

    def increment(self, name: str, value: int = 1) -> None:
        """
        Increment.

        Args:
            name (str): name of the object.
            value (int): numeric value for value. Defaults to ``1``.
        """
        self._counters[name] = self._counters.get(name, 0) + value
        self.record(name, self._counters[name])

    def start_timer(self, name: str) -> None:
        """
        Start timer.

        Args:
            name (str): name of the object.
        """
        self._timers[name] = time.time()

    def stop_timer(self, name: str) -> float:
        """
        Stop timer.

        Args:
            name (str): name of the object.

        Returns:
            float: the computed numeric value.
        """
        if name in self._timers:
            duration = time.time() - self._timers[name]
            del self._timers[name]
            self.record(f"{name}_duration", duration)
            return duration
        return 0.0

    def add_alert(self, name: str, condition: str, threshold: float) -> None:
        """
        Add alert.

        Args:
            name (str): name of the object.
            condition (str): condition string.
            threshold (float): numeric value for threshold.
        """
        self._alerts.append(
            Alert(
                name=name,
                condition=condition,
                threshold=threshold,
            )
        )

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
        """
        Return the metric.

        Args:
            name (str): name of the object.
            limit (int): maximum number of items to return. Defaults to ``100``.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        metrics = self._metrics.get(name, [])[-limit:]
        return [{"value": m.value, "timestamp": m.timestamp, "tags": m.tags} for m in metrics]

    def get_counter(self, name: str) -> int:
        """
        Return the counter.

        Args:
            name (str): name of the object.

        Returns:
            int: the computed numeric value.
        """
        return self._counters.get(name, 0)

    def get_summary(self) -> dict[str, Any]:
        """
        Return the summary.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
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
        """
        Return the alerts.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        return [
            {
                "name": a.name,
                "condition": a.condition,
                "threshold": a.threshold,
                "current": a.current_value,
            }
            for a in self._alerts
            if a.triggered
        ]
