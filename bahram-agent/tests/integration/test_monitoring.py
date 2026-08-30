"""Tests for monitoring status report and doctor check."""
from __future__ import annotations

import pytest

from bahram.monitoring.status import status_report, doctor_check, RuntimeStatus


class TestStatusReportReturnsDict:
    def test_returns_dict(self) -> None:
        result = status_report()
        assert isinstance(result, dict)

    def test_has_expected_keys(self) -> None:
        result = status_report()
        expected_keys = {
            "active_runs",
            "active_jobs",
            "active_subagents",
            "provider_health",
            "tool_success_rate",
            "budget_usage",
            "circuit_breaker_states",
            "error_counts",
            "estimated_cost",
        }
        assert expected_keys == set(result.keys())

    def test_tool_success_rate_default_zero(self) -> None:
        result = status_report()
        assert result["tool_success_rate"] == 0.0

    def test_estimated_cost_default_zero(self) -> None:
        result = status_report()
        assert result["estimated_cost"] == 0.0


class TestStatusReportWithEngine:
    def test_collects_tool_stats(self) -> None:
        class FakeExecutor:
            _log = [
                {"tool": "bash", "status": "success", "timestamp": 1.0},
                {"tool": "bash", "status": "success", "timestamp": 2.0},
                {"tool": "read", "status": "error", "timestamp": 3.0, "error": "fail"},
            ]

        class FakeEngine:
            _tool_executor = FakeExecutor()
            _circuit_breaker = None
            providers = {}
            tools = {}

        result = status_report(engine=FakeEngine())
        assert result["tool_success_rate"] == pytest.approx(2.0 / 3.0, rel=1e-6)

    def test_collects_circuit_breaker_states(self) -> None:
        class FakeBreaker:
            def get_status(self):
                return {"anthropic": {"state": "closed", "failures": 0, "successes": 10, "last_failure": 0.0}}

        class FakeEngine:
            _tool_executor = None
            _circuit_breaker = FakeBreaker()
            providers = {}
            tools = {}

        result = status_report(engine=FakeEngine())
        assert "anthropic" in result["circuit_breaker_states"]
        assert result["circuit_breaker_states"]["anthropic"]["state"] == "closed"


class TestDoctorCheckIdentifiesHealthy:
    def test_all_healthy_when_provided(self) -> None:
        class FakeEngine:
            providers = {"anthropic": None}
            tools = {"bash": None}
            _circuit_breaker = None

        class FakeJobEngine:
            def get_queue_depth(self):
                return {"running": 1}

        class FakeSubagentEngine:
            def get_active_count(self):
                return 2

        class FakeBudgetManager:
            class config:
                max_cost_usd = 5.0

        result = doctor_check(
            engine=FakeEngine(),
            job_engine=FakeJobEngine(),
            subagent_engine=FakeSubagentEngine(),
            budget_manager=FakeBudgetManager(),
        )
        assert len(result) == 5
        healthy_names = {c["name"] for c in result if c["healthy"]}
        assert "providers" in healthy_names
        assert "tools" in healthy_names
        assert "job_engine" in healthy_names
        assert "subagent_engine" in healthy_names
        assert "budget_manager" in healthy_names

    def test_unhealthy_when_no_providers(self) -> None:
        class FakeEngine:
            providers = {}
            tools = {}
            _circuit_breaker = None

        result = doctor_check(engine=FakeEngine())
        providers_check = next(c for c in result if c["name"] == "providers")
        assert providers_check["healthy"] is False

    def test_unhealthy_when_engine_missing(self) -> None:
        result = doctor_check()
        engine_check = next(c for c in result if c["name"] == "engine")
        assert engine_check["healthy"] is False

    def test_unhealthy_when_job_engine_missing(self) -> None:
        result = doctor_check()
        job_check = next(c for c in result if c["name"] == "job_engine")
        assert job_check["healthy"] is False
