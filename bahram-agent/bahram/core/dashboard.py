"""
Dashboard.

Public objects: ``DashboardStats``, ``Dashboard``.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DashboardStats:
    """
    Dashboard stats.

    Attributes:
        total_messages (int): numeric value for total messages.
        total_tokens (int): numeric value for total tokens.
        total_cost (float): numeric value for total cost.
        active_platforms (list[str]): collection of active platforms.
        uptime (float): numeric value for uptime.
        last_activity (float): numeric value for last activity.
        errors (int): numeric value for errors.
        success_rate (float): numeric value for success rate.
    """

    total_messages: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    active_platforms: list[str] = field(default_factory=list)
    uptime: float = 0.0
    last_activity: float = 0.0
    errors: int = 0
    success_rate: float = 100.0


class Dashboard:
    """
    Dashboard.
    """

    def __init__(self, data_dir: str = "data/gateway") -> None:
        """
        Initialise a Dashboard instance.

        Args:
            data_dir (str): directory that holds the on-disk state. Defaults to ``'data/gateway'``.
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._stats = DashboardStats()
        self._start_time = time.time()
        self._load()

    def _load(self) -> None:
        stats_file = self.data_dir / "dashboard_stats.json"
        if stats_file.exists():
            try:
                with open(stats_file) as f:
                    data = json.load(f)
                self._stats = DashboardStats(**data)
            except Exception as e:
                logger.warning(f"Failed to load dashboard stats: {e}")

    def _save(self) -> None:
        stats_file = self.data_dir / "dashboard_stats.json"
        self._stats.uptime = time.time() - self._start_time
        data = {
            "total_messages": self._stats.total_messages,
            "total_tokens": self._stats.total_tokens,
            "total_cost": self._stats.total_cost,
            "active_platforms": self._stats.active_platforms,
            "uptime": self._stats.uptime,
            "last_activity": self._stats.last_activity,
            "errors": self._stats.errors,
            "success_rate": self._stats.success_rate,
        }
        with open(stats_file, "w") as f:
            json.dump(data, f, indent=2)

    def record_message(self, platform: str, tokens: int = 0, cost: float = 0.0) -> None:
        """
        Record message.

        Args:
            platform (str): platform string.
            tokens (int): numeric value for tokens. Defaults to ``0``.
            cost (float): numeric value for cost. Defaults to ``0.0``.
        """
        self._stats.total_messages += 1
        self._stats.total_tokens += tokens
        self._stats.total_cost += cost
        self._stats.last_activity = time.time()

        if platform not in self._stats.active_platforms:
            self._stats.active_platforms.append(platform)

        self._save()

    def record_error(self) -> None:
        """
        Record error.
        """
        self._stats.errors += 1
        if self._stats.total_messages > 0:
            self._stats.success_rate = (
                (self._stats.total_messages - self._stats.errors) / self._stats.total_messages * 100
            )
        self._save()

    def get_stats(self) -> dict[str, Any]:
        """
        Return the stats.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        self._stats.uptime = time.time() - self._start_time
        return {
            "total_messages": self._stats.total_messages,
            "total_tokens": self._stats.total_tokens,
            "total_cost": self._stats.total_cost,
            "active_platforms": self._stats.active_platforms,
            "uptime_hours": self._stats.uptime / 3600,
            "last_activity": self._stats.last_activity,
            "errors": self._stats.errors,
            "success_rate": self._stats.success_rate,
        }

    def get_health(self) -> str:
        """
        Return the health.

        Returns:
            str: the rendered string.
        """
        if self._stats.success_rate > 99:
            return "healthy"
        elif self._stats.success_rate > 95:
            return "degraded"
        else:
            return "unhealthy"

    def format_dashboard(self) -> str:
        """
        Format dashboard.

        Returns:
            str: the rendered string.
        """
        stats = self.get_stats()
        health = self.get_health()
        health_emoji = {"healthy": "🟢", "degraded": "🟡", "unhealthy": "🔴"}

        lines = [
            f"{health_emoji.get(health, '⚪')} **Bahram Agent Dashboard**",
            f"Health: {health.upper()}",
            f"Uptime: {stats['uptime_hours']:.1f}h",
            f"Messages: {stats['total_messages']}",
            f"Tokens: {stats['total_tokens']:,}",
            f"Cost: ${stats['total_cost']:.2f}",
            f"Errors: {stats['errors']}",
            f"Success Rate: {stats['success_rate']:.1f}%",
            f"Active Platforms: {', '.join(stats['active_platforms']) or 'none'}",
        ]
        return "\n".join(lines)

    def reset(self) -> None:
        """
        Reset.
        """
        self._stats = DashboardStats()
        self._start_time = time.time()
        self._save()
