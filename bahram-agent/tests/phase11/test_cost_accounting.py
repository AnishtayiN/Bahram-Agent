"""Phase 11: Cost accounting tests.

Tests that cost estimation works correctly for known and unknown models.
"""

from __future__ import annotations

from bahram.autonomy.cost import MODEL_PRICING, estimate_cost, get_pricing_info


class TestCostAccounting:
    """Verify cost estimation behavior."""

    def test_known_model_cost(self):
        """Known model should return positive cost."""
        cost = estimate_cost(
            "anthropic/claude-sonnet-4-20250514", input_tokens=1000, output_tokens=500
        )
        assert cost > 0
        expected = (1000 / 1000) * 0.003 + (500 / 1000) * 0.015
        assert abs(cost - expected) < 0.001

    def test_unknown_model_cost(self):
        """Unknown model should return 0.0."""
        cost = estimate_cost("unknown/model", input_tokens=1000, output_tokens=500)
        assert cost == 0.0

    def test_zero_tokens_cost(self):
        """Zero tokens should return zero cost."""
        cost = estimate_cost("anthropic/claude-sonnet-4-20250514", input_tokens=0, output_tokens=0)
        assert cost == 0.0

    def test_all_known_models_have_pricing(self):
        """All registered models should have pricing info."""
        for model in MODEL_PRICING:
            info = get_pricing_info(model)
            assert info is not None
            assert "input_per_1k" in info
            assert "output_per_1k" in info

    def test_cost_scales_with_tokens(self):
        """Cost should scale proportionally with token count."""
        cost1 = estimate_cost("openai/gpt-4o", input_tokens=1000, output_tokens=0)
        cost2 = estimate_cost("openai/gpt-4o", input_tokens=2000, output_tokens=0)
        assert abs(cost2 - cost1 * 2) < 0.0001

    def test_output_more_expensive_than_input(self):
        """Output tokens should be more expensive than input tokens."""
        cost_in = estimate_cost(
            "anthropic/claude-sonnet-4-20250514", input_tokens=1000, output_tokens=0
        )
        cost_out = estimate_cost(
            "anthropic/claude-sonnet-4-20250514", input_tokens=0, output_tokens=1000
        )
        assert cost_out > cost_in

    def test_pricing_info_returns_none_for_unknown(self):
        """Unknown model should return None pricing."""
        info = get_pricing_info("nonexistent/model")
        assert info is None

    def test_cost_is_float(self):
        """Cost should always be a float."""
        cost = estimate_cost("openai/gpt-4o", input_tokens=100, output_tokens=100)
        assert isinstance(cost, float)
