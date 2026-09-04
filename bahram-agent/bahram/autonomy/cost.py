"""Phase 11: Cost accounting implementation.

Adds real cost estimation to BudgetManager based on provider/model pricing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

MODEL_PRICING: dict[str, dict[str, float]] = {
    "anthropic/claude-sonnet-4-20250514": {"input_per_1k": 0.003, "output_per_1k": 0.015},
    "anthropic/claude-3-5-sonnet-20241022": {"input_per_1k": 0.003, "output_per_1k": 0.015},
    "anthropic/claude-3-haiku-20240307": {"input_per_1k": 0.00025, "output_per_1k": 0.00125},
    "openai/gpt-4o": {"input_per_1k": 0.0025, "output_per_1k": 0.01},
    "openai/gpt-4o-mini": {"input_per_1k": 0.00015, "output_per_1k": 0.0006},
    "openai/gpt-3.5-turbo": {"input_per_1k": 0.0005, "output_per_1k": 0.0015},
    "google/gemini-2.0-flash": {"input_per_1k": 0.000075, "output_per_1k": 0.0003},
    "google/gemini-1.5-pro": {"input_per_1k": 0.00125, "output_per_1k": 0.005},
}


@dataclass
class CostEntry:
    """
    Cost entry.

    Attributes:
        model (str): model identifier in ``provider/model`` form.
        input_tokens (int): numeric value for input tokens.
        output_tokens (int): numeric value for output tokens.
        input_cost (float): numeric value for input cost.
        output_cost (float): numeric value for output cost.
        total_cost (float): numeric value for total cost.
        timestamp (float): numeric value for timestamp.
    """

    model: str
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    timestamp: float = 0.0


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD for a model call. Returns 0.0 if pricing unknown."""
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        provider = model.split("/")[0] if "/" in model else ""
        for key in MODEL_PRICING:
            if key.startswith(provider + "/"):
                pricing = MODEL_PRICING[key]
                break
    if not pricing:
        return 0.0

    input_cost = (input_tokens / 1000.0) * pricing["input_per_1k"]
    output_cost = (output_tokens / 1000.0) * pricing["output_per_1k"]
    return input_cost + output_cost


def get_pricing_info(model: str) -> dict[str, Any] | None:
    """Get pricing information for a model."""
    return MODEL_PRICING.get(model)
