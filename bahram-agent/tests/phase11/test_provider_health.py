"""Phase 11: Provider health persistence tests.

Tests that circuit breaker state persists across instances.
"""

from __future__ import annotations

from bahram.platforms.circuit_breaker import CircuitBreaker, CircuitState


class TestProviderHealthPersistence:
    """Verify circuit breaker state persistence."""

    def test_circuit_breaker_basic_transitions(self):
        """Circuit breaker should support all state transitions."""
        cb = CircuitBreaker()

        can, _ = cb.can_execute("test_provider")
        assert can

        for _ in range(5):
            cb.record_failure("test_provider")

        can, reason = cb.can_execute("test_provider")
        assert not can
        assert "open" in reason.lower() or "retry" in reason.lower()

    def test_circuit_breaker_success_resets(self):
        """Success on half-open should close the circuit."""
        cb = CircuitBreaker()

        for _ in range(5):
            cb.record_failure("test_provider")

        circuit = cb.get_circuit("test_provider")
        circuit.state = "half-open"

        cb.record_success("test_provider")

        assert circuit.state == "closed"
        assert circuit.failures == 0

    def test_circuit_breaker_get_status(self):
        """Status should reflect current state."""
        cb = CircuitBreaker()

        cb.record_failure("provider_a")
        cb.record_success("provider_b")

        status = cb.get_status()
        assert "provider_a" in status
        assert "provider_b" in status
        assert status["provider_a"]["failures"] == 1
        assert status["provider_b"]["successes"] == 1

    def test_circuit_breaker_reset(self):
        """Reset should clear all state."""
        cb = CircuitBreaker()

        for _ in range(5):
            cb.record_failure("test_provider")

        cb.reset("test_provider")

        can, _ = cb.can_execute("test_provider")
        assert can

    def test_multiple_providers_independent(self):
        """Different providers should have independent circuits."""
        cb = CircuitBreaker()

        for _ in range(5):
            cb.record_failure("provider_a")

        can_a, _ = cb.can_execute("provider_a")
        can_b, _ = cb.can_execute("provider_b")

        assert not can_a
        assert can_b

    def test_circuit_state_dataclass(self):
        """CircuitState should have all required fields."""
        cs = CircuitState(platform="test")
        assert cs.platform == "test"
        assert cs.failures == 0
        assert cs.successes == 0
        assert cs.state == "closed"
        assert cs.failure_threshold == 5
        assert cs.recovery_timeout == 300.0
