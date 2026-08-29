"""Platform circuit breaker for Bahram Agent."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CircuitState:
    """Circuit breaker state."""

    platform: str
    failures: int = 0
    successes: int = 0
    last_failure: float = 0.0
    state: str = "closed"  # closed, open, half-open
    failure_threshold: int = 5
    recovery_timeout: float = 300.0  # 5 minutes


class CircuitBreaker:
    """Circuit breaker for platform adapters."""

    def __init__(self) -> None:
        self._circuits: dict[str, CircuitState] = {}
        self._failure_threshold = 5
        self._recovery_timeout = 300.0

    def get_circuit(self, platform: str) -> CircuitState:
        """Get circuit state for platform."""
        if platform not in self._circuits:
            self._circuits[platform] = CircuitState(platform=platform)
        return self._circuits[platform]

    def record_success(self, platform: str) -> None:
        """Record a successful call."""
        circuit = self.get_circuit(platform)
        circuit.successes += 1

        if circuit.state == "half-open":
            circuit.state = "closed"
            circuit.failures = 0
            logger.info(f"Circuit closed for {platform}")

    def record_failure(self, platform: str) -> None:
        """Record a failed call."""
        circuit = self.get_circuit(platform)
        circuit.failures += 1
        circuit.last_failure = time.time()

        if circuit.failures >= circuit.failure_threshold:
            circuit.state = "open"
            logger.warning(f"Circuit opened for {platform} after {circuit.failures} failures")

    def can_execute(self, platform: str) -> tuple[bool, str]:
        """Check if execution is allowed."""
        circuit = self.get_circuit(platform)

        if circuit.state == "closed":
            return True, "Circuit closed"

        if circuit.state == "open":
            # Check if recovery timeout has passed
            if time.time() - circuit.last_failure > circuit.recovery_timeout:
                circuit.state = "half-open"
                logger.info(f"Circuit half-open for {platform}")
                return True, "Circuit half-open"
            else:
                remaining = circuit.recovery_timeout - (time.time() - circuit.last_failure)
                return False, f"Circuit open, retry in {remaining:.0f}s"

        # Half-open: allow one request
        return True, "Circuit half-open"

    def reset(self, platform: str) -> None:
        """Reset circuit for platform."""
        if platform in self._circuits:
            del self._circuits[platform]
            logger.info(f"Circuit reset for {platform}")

    def get_status(self) -> dict[str, dict]:
        """Get status of all circuits."""
        return {
            platform: {
                "state": circuit.state,
                "failures": circuit.failures,
                "successes": circuit.successes,
                "last_failure": circuit.last_failure,
            }
            for platform, circuit in self._circuits.items()
        }
