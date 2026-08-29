"""Platform circuit breaker for Bahram Agent."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreakerState:
    """State of a circuit breaker."""

    platform: str
    state: str = "closed"  # closed, open, half-open
    failure_count: int = 0
    last_failure: float = 0
    last_success: float = 0
    trip_count: int = 0


class CircuitBreaker:
    """Circuit breaker for platform adapters."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 300,  # 5 minutes
        half_open_max: int = 3,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max
        self._breakers: dict[str, CircuitBreakerState] = {}

    def _get_breaker(self, platform: str) -> CircuitBreakerState:
        """Get or create breaker for platform."""
        if platform not in self._breakers:
            self._breakers[platform] = CircuitBreakerState(platform=platform)
        return self._breakers[platform]

    def record_success(self, platform: str) -> None:
        """Record a success."""
        breaker = self._get_breaker(platform)
        breaker.last_success = time.time()

        if breaker.state == "half-open":
            breaker.state = "closed"
            breaker.failure_count = 0
            logger.info(f"Circuit breaker closed for {platform}")

    def record_failure(self, platform: str) -> None:
        """Record a failure."""
        breaker = self._get_breaker(platform)
        breaker.failure_count += 1
        breaker.last_failure = time.time()

        if breaker.failure_count >= self.failure_threshold:
            if breaker.state != "open":
                breaker.state = "open"
                breaker.trip_count += 1
                logger.warning(f"Circuit breaker tripped for {platform}")

    def should_allow(self, platform: str) -> bool:
        """Check if request should be allowed."""
        breaker = self._get_breaker(platform)

        if breaker.state == "closed":
            return True

        if breaker.state == "open":
            # Check if recovery timeout has passed
            if time.time() - breaker.last_failure > self.recovery_timeout:
                breaker.state = "half-open"
                logger.info(f"Circuit breaker half-open for {platform}")
                return True
            return False

        if breaker.state == "half-open":
            # Allow limited requests
            return True

        return False

    def get_state(self, platform: str) -> dict:
        """Get breaker state."""
        breaker = self._get_breaker(platform)
        return {
            "platform": breaker.platform,
            "state": breaker.state,
            "failure_count": breaker.failure_count,
            "trip_count": breaker.trip_count,
        }

    def reset(self, platform: str) -> None:
        """Reset breaker for platform."""
        if platform in self._breakers:
            self._breakers[platform] = CircuitBreakerState(platform=platform)

    def get_all_states(self) -> list[dict]:
        """Get all breaker states."""
        return [self.get_state(p) for p in self._breakers]
