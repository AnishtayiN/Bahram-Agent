"""Tests for cost accounting integration in BudgetManager."""

from __future__ import annotations

import pytest

from bahram.autonomy.budget import BudgetConfig, BudgetManager


class TestCostInRecordModelCall:
    def test_known_model_records_cost(self) -> None:
        mgr = BudgetManager()
        mgr.record_model_call(
            run_id="r1", model="openai/gpt-4o", input_tokens=1000, output_tokens=500
        )
        usage = mgr.get_run_budget("r1")
        assert usage.cost_usd > 0
        assert usage.estimated_cost_usd > 0
        assert usage.model_calls == 1

    def test_unknown_model_reports_zero_cost(self) -> None:
        mgr = BudgetManager()
        mgr.record_model_call(
            run_id="r1", model="mystery/model-x", input_tokens=1000, output_tokens=500
        )
        usage = mgr.get_run_budget("r1")
        assert usage.cost_usd == 0.0
        assert usage.estimated_cost_usd == 0.0

    def test_empty_model_reports_zero_cost(self) -> None:
        mgr = BudgetManager()
        mgr.record_model_call(run_id="r1", model="", input_tokens=1000, output_tokens=500)
        usage = mgr.get_run_budget("r1")
        assert usage.cost_usd == 0.0

    def test_cost_accumulates_across_calls(self) -> None:
        mgr = BudgetManager()
        mgr.record_model_call(
            run_id="r1", model="openai/gpt-4o", input_tokens=1000, output_tokens=500
        )
        first_cost = mgr.get_run_budget("r1").cost_usd
        mgr.record_model_call(
            run_id="r1", model="openai/gpt-4o", input_tokens=1000, output_tokens=500
        )
        second_cost = mgr.get_run_budget("r1").cost_usd
        assert second_cost == pytest.approx(first_cost * 2, rel=1e-6)

    def test_cost_accumulates_in_session(self) -> None:
        mgr = BudgetManager()
        mgr.record_model_call(
            run_id="r1",
            session_id="s1",
            model="openai/gpt-4o",
            input_tokens=1000,
            output_tokens=500,
        )
        first = mgr.get_session_budget("s1").cost_usd
        mgr.record_model_call(
            run_id="r1",
            session_id="s1",
            model="openai/gpt-4o",
            input_tokens=1000,
            output_tokens=500,
        )
        second = mgr.get_session_budget("s1").cost_usd
        assert second == pytest.approx(first * 2, rel=1e-6)


class TestCostWarningThreshold:
    def test_warning_triggered_at_threshold(self) -> None:
        config = BudgetConfig(max_cost_usd=0.01, warning_threshold=0.5)
        mgr = BudgetManager(config)
        warnings = mgr.record_model_call(
            run_id="r1", model="openai/gpt-4o", input_tokens=5000, output_tokens=5000
        )
        cost_warnings = [w for w in warnings if "cost" in w.lower()]
        assert len(cost_warnings) > 0

    def test_no_warning_below_threshold(self) -> None:
        config = BudgetConfig(max_cost_usd=100.0, warning_threshold=0.8)
        mgr = BudgetManager(config)
        warnings = mgr.record_model_call(
            run_id="r1", model="openai/gpt-4o", input_tokens=10, output_tokens=10
        )
        cost_warnings = [w for w in warnings if "cost" in w.lower()]
        assert len(cost_warnings) == 0


class TestCostHardLimit:
    def test_hard_limit_enforced_via_check_cost_budget(self) -> None:
        config = BudgetConfig(max_cost_usd=0.01, warning_threshold=0.8)
        mgr = BudgetManager(config)
        for _ in range(200):
            mgr.record_model_call(
                run_id="r1", model="openai/gpt-4o", input_tokens=500, output_tokens=500
            )
        result = mgr.check_cost_budget("r1")
        assert result["hard_exceeded"] is True
        assert result["can_continue"] is False

    def test_soft_limit_not_yet_hard(self) -> None:
        config = BudgetConfig(max_cost_usd=0.01, warning_threshold=0.8)
        mgr = BudgetManager(config)
        mgr.record_model_call(
            run_id="r1", model="openai/gpt-4o", input_tokens=200, output_tokens=200
        )
        result = mgr.check_cost_budget("r1")
        # cost should be small, well under hard limit
        assert result["hard_exceeded"] is False
        assert result["can_continue"] is True

    def test_custom_max_cost_override(self) -> None:
        mgr = BudgetManager()
        mgr.record_model_call(
            run_id="r1", model="openai/gpt-4o", input_tokens=1000, output_tokens=500
        )
        result = mgr.check_cost_budget("r1", max_cost=0.0)
        assert result["hard_exceeded"] is True


class TestCheckBudgetIncludesCost:
    def test_check_budget_exceeds_cost(self) -> None:
        config = BudgetConfig(max_cost_usd=0.001)
        mgr = BudgetManager(config)
        for _ in range(10):
            mgr.record_model_call(
                run_id="r1", model="openai/gpt-4o", input_tokens=500, output_tokens=500
            )
        result = mgr.check_budget("r1")
        assert "cost_usd" in result["exceeded"]


class TestGetAllUsageIncludesCost:
    def test_all_usage_has_cost(self) -> None:
        mgr = BudgetManager()
        mgr.record_model_call(
            run_id="r1", model="openai/gpt-4o", input_tokens=1000, output_tokens=500
        )
        all_usage = mgr.get_all_usage()
        run_data = all_usage["runs"]["r1"]
        assert "cost_usd" in run_data
        assert run_data["cost_usd"] > 0


class TestCostReset:
    def test_reset_run_clears_cost(self) -> None:
        mgr = BudgetManager()
        mgr.record_model_call(
            run_id="r1", model="openai/gpt-4o", input_tokens=1000, output_tokens=500
        )
        assert mgr.get_run_budget("r1").cost_usd > 0
        mgr.reset_run("r1")
        assert mgr.get_run_budget("r1").cost_usd == 0.0

    def test_reset_session_clears_cost(self) -> None:
        mgr = BudgetManager()
        mgr.record_model_call(
            run_id="r1",
            session_id="s1",
            model="openai/gpt-4o",
            input_tokens=1000,
            output_tokens=500,
        )
        assert mgr.get_session_budget("s1").cost_usd > 0
        mgr.reset_session("s1")
        assert mgr.get_session_budget("s1").cost_usd == 0.0


class TestCostBudgetWarningMessages:
    def test_warning_in_check_cost_budget(self) -> None:
        config = BudgetConfig(max_cost_usd=0.01, warning_threshold=0.5)
        mgr = BudgetManager(config)
        # Generate enough cost to cross the warning threshold
        for _ in range(200):
            mgr.record_model_call(
                run_id="r1", model="openai/gpt-4o", input_tokens=100, output_tokens=100
            )
        result = mgr.check_cost_budget("r1")
        assert len(result["warnings"]) > 0
        assert "Cost approaching limit" in result["warnings"][0]
