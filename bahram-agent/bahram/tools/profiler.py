"""
Profiler.

Public objects: ``ProfileResult``, ``Profiler``, ``FunctionTimer``.
"""

from __future__ import annotations

import cProfile
import io
import logging
import pstats
import time
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProfileResult:
    """
    Profile result.

    Attributes:
        function (str): function string.
        calls (int): numeric value for calls.
        total_time (float): numeric value for total time.
        per_call (float): numeric value for per call.
    """

    function: str
    calls: int
    total_time: float
    per_call: float


class Profiler:
    """
    Profiler.
    """

    def __init__(self) -> None:
        """
        Initialise a Profiler instance.
        """
        self._profiler = cProfile.Profile()
        self._results: list[ProfileResult] = []

    def start(self) -> None:
        """
        Start the component and acquire any resources it needs.
        """
        self._profiler.enable()

    def stop(self) -> None:
        """
        Stop the component and release any resources it holds.
        """
        self._profiler.disable()

    def get_stats(self, top_n: int = 20) -> list[ProfileResult]:
        """
        Return the stats.

        Args:
            top_n (int): numeric value for top n. Defaults to ``20``.

        Returns:
            list[ProfileResult]: a sequence of ProfileResult entries (empty when there is nothing to
                report).
        """
        # pstats raises TypeError when handed a Profile that recorded no
        # calls - right after reset(), or when start()/stop() bracketed no
        # work.  There is nothing to report in that case.
        if not self._profiler.getstats():
            return []

        stream = io.StringIO()
        stats = pstats.Stats(self._profiler, stream=stream)
        stats.sort_stats("cumulative")
        stats.print_stats(top_n)

        results = []
        for key, value in stats.stats.items():
            filename, line, func = key
            cc, nc, tt, ct, callers = value
            results.append(
                ProfileResult(
                    function=f"{filename}:{line}({func})",
                    calls=nc,
                    total_time=tt,
                    per_call=tt / nc if nc > 0 else 0,
                )
            )

        return sorted(results, key=lambda x: x.total_time, reverse=True)

    def format_report(self, results: list[ProfileResult]) -> str:
        """
        Format report.

        Args:
            results (list[ProfileResult]): collection of results.

        Returns:
            str: the rendered string.
        """
        lines = ["## Profile Report", ""]
        lines.append(f"{'Function':<60} {'Calls':>8} {'Total':>10} {'Per Call':>10}")
        lines.append("-" * 90)

        for r in results[:20]:
            lines.append(
                f"{r.function[:60]:<60} {r.calls:>8} {r.total_time:>10.4f} {r.per_call:>10.6f}"
            )

        return "\n".join(lines)

    def reset(self) -> None:
        """
        Reset.
        """
        self._profiler = cProfile.Profile()
        self._results.clear()


class FunctionTimer:
    """
    Function timer.
    """

    def __init__(self) -> None:
        """
        Initialise a FunctionTimer instance.
        """
        self._timings: dict[str, list[float]] = {}

    def time(self, func: Callable) -> Callable:
        """
        Time.

        Args:
            func (Callable): callable used for func.

        Returns:
            Callable: the resulting Callable.
        """
        import functools

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            result = await func(*args, **kwargs)
            duration = time.time() - start

            name = func.__qualname__
            if name not in self._timings:
                self._timings[name] = []
            self._timings[name].append(duration)

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start

            name = func.__qualname__
            if name not in self._timings:
                self._timings[name] = []
            self._timings[name].append(duration)

            return result

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    def get_report(self) -> str:
        """
        Return the report.

        Returns:
            str: the rendered string.
        """
        lines = ["## Timing Report", ""]
        lines.append(f"{'Function':<50} {'Calls':>8} {'Total':>10} {'Avg':>10}")
        lines.append("-" * 80)

        for name, timings in sorted(self._timings.items(), key=lambda x: sum(x[1]), reverse=True):
            total = sum(timings)
            avg = total / len(timings)
            lines.append(f"{name[:50]:<50} {len(timings):>8} {total:>10.4f} {avg:>10.6f}")

        return "\n".join(lines)

    def reset(self) -> None:
        """
        Reset.
        """
        self._timings.clear()
