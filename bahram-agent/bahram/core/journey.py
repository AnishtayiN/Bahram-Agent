"""
Journey.

Public objects: ``CurveType``, ``LearningPoint``, ``LearningCurve``, ``LearningJourney``.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CurveType(str, Enum):
    """
    Curve type.
    """

    PLATEAU = "plateau"
    CLIMBING = "climbing"
    DECLINING = "declining"
    MASTERY = "mastery"


@dataclass
class LearningPoint:
    """
    Learning point.

    Attributes:
        timestamp (float): numeric value for timestamp.
        metric (float): numeric value for metric.
        description (str): human readable description.
        context (dict): mapping of context.
    """

    timestamp: float
    metric: float
    description: str
    context: dict = field(default_factory=dict)


@dataclass
class LearningCurve:
    """
    Learning curve.

    Attributes:
        curve_type (CurveType): curve type.
        confidence (float): numeric value for confidence.
        description (str): human readable description.
        suggested_action (str): suggested action string.
    """

    curve_type: CurveType
    confidence: float
    description: str
    suggested_action: str


class LearningJourney:
    """
    Learning journey.
    """

    def __init__(self, data_dir: str = "data/memory") -> None:
        """
        Initialise a LearningJourney instance.

        Args:
            data_dir (str): directory that holds the on-disk state. Defaults to ``'data/memory'``.
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._points: list[LearningPoint] = []
        self._curves: list[LearningCurve] = []
        self._load()

    def _load(self) -> None:
        journey_file = self.data_dir / "journey.json"
        if journey_file.exists():
            try:
                with open(journey_file) as f:
                    data = json.load(f)
                self._points = [LearningPoint(**p) for p in data.get("points", [])]
                self._curves = [LearningCurve(**c) for c in data.get("curves", [])]
            except Exception as e:
                logger.warning(f"Failed to load journey: {e}")

    def _save(self) -> None:
        journey_file = self.data_dir / "journey.json"
        data = {
            "points": [
                {
                    "timestamp": p.timestamp,
                    "metric": p.metric,
                    "description": p.description,
                    "context": p.context,
                }
                for p in self._points
            ],
            "curves": [
                {
                    "curve_type": c.curve_type.value,
                    "confidence": c.confidence,
                    "description": c.description,
                    "suggested_action": c.suggested_action,
                }
                for c in self._curves
            ],
        }
        with open(journey_file, "w") as f:
            json.dump(data, f, indent=2)

    def record(self, metric: float, description: str = "", context: dict = None) -> None:
        """
        Record.

        Args:
            metric (float): numeric value for metric.
            description (str): human readable description. Defaults to ``''``.
            context (dict): mapping of context. Defaults to ``None``.
        """
        point = LearningPoint(
            timestamp=time.time(),
            metric=metric,
            description=description,
            context=context or {},
        )
        self._points.append(point)
        self._save()

        if len(self._points) >= 3:
            curve = self._detect_curve()
            if curve and (not self._curves or self._curves[-1].curve_type != curve.curve_type):
                self._curves.append(curve)
                self._save()
                logger.info(
                    f"Learning curve detected: {curve.curve_type.value} ({curve.confidence:.0%})"
                )

    def _detect_curve(self) -> LearningCurve | None:
        if len(self._points) < 3:
            return None

        recent = self._points[-10:]
        metrics = [p.metric for p in recent]

        if len(metrics) < 2:
            return None

        first_half = metrics[: len(metrics) // 2]
        second_half = metrics[len(metrics) // 2 :]

        avg_first = sum(first_half) / len(first_half) if first_half else 0
        avg_second = sum(second_half) / len(second_half) if second_half else 0

        diff = avg_second - avg_first
        total = max(abs(avg_first), abs(avg_second), 1)
        change_pct = diff / total

        if abs(change_pct) < 0.05:
            curve_type = CurveType.PLATEAU
            confidence = 0.8
            description = "Performance is stable"
            action = "Consider trying more challenging tasks"
        elif change_pct > 0.2:
            curve_type = CurveType.MASTERY
            confidence = 0.9
            description = "Excellent improvement!"
            action = "Ready for advanced concepts"
        elif change_pct > 0.05:
            curve_type = CurveType.CLIMBING
            confidence = 0.7
            description = "Steady improvement"
            action = "Continue current approach"
        elif change_pct < -0.2:
            curve_type = CurveType.DECLINING
            confidence = 0.9
            description = "Performance declining"
            action = "Review recent mistakes and adjust"
        else:
            curve_type = CurveType.DECLINING
            confidence = 0.6
            description = "Slight decline detected"
            action = "Monitor and consider adjustments"

        return LearningCurve(
            curve_type=curve_type,
            confidence=confidence,
            description=description,
            suggested_action=action,
        )

    def get_summary(self) -> dict[str, Any]:
        """
        Return the summary.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        if not self._points:
            return {"status": "no_data"}

        metrics = [p.metric for p in self._points]
        return {
            "total_points": len(self._points),
            "current_metric": metrics[-1],
            "best_metric": max(metrics),
            "worst_metric": min(metrics),
            "average_metric": sum(metrics) / len(metrics),
            "current_curve": self._curves[-1].curve_type.value if self._curves else "unknown",
            "trend": "improving"
            if metrics[-1] > metrics[0]
            else "declining"
            if metrics[-1] < metrics[0]
            else "stable",
        }

    def get_curve_history(self) -> list[dict]:
        """
        Return the curve history.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        return [
            {
                "curve_type": c.curve_type.value,
                "confidence": c.confidence,
                "description": c.description,
                "suggested_action": c.suggested_action,
            }
            for c in self._curves
        ]

    def reset(self) -> None:
        """
        Reset.
        """
        self._points.clear()
        self._curves.clear()
        self._save()
