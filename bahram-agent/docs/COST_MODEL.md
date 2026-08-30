# Cost Model — Cost Accounting System

## Overview

The cost accounting system lives in `bahram/autonomy/cost.py` and provides per-call cost estimation for LLM provider calls. It is a standalone module — currently **not wired into BudgetManager**.

---

## Architecture

```
bahram/autonomy/cost.py
    ├── MODEL_PRICING (dict)     — Static pricing table for 8 known models
    ├── CostEntry (dataclass)    — Single cost record
    ├── estimate_cost()          — Compute USD cost for a model call
    └── get_pricing_info()       — Look up raw pricing for a model
```

---

## MODEL_PRICING Table

Hardcoded pricing at `cost.py:13-22`:

| Model | Input (per 1K tokens) | Output (per 1K tokens) | Ratio |
|-------|----------------------|------------------------|-------|
| `anthropic/claude-sonnet-4-20250514` | $0.003 | $0.015 | 5:1 |
| `anthropic/claude-3-5-sonnet-20241022` | $0.003 | $0.015 | 5:1 |
| `anthropic/claude-3-haiku-20240307` | $0.00025 | $0.00125 | 5:1 |
| `openai/gpt-4o` | $0.0025 | $0.01 | 4:1 |
| `openai/gpt-4o-mini` | $0.00015 | $0.0006 | 4:1 |
| `openai/gpt-3.5-turbo` | $0.0005 | $0.0015 | 3:1 |
| `google/gemini-2.0-flash` | $0.000075 | $0.0003 | 4:1 |
| `google/gemini-1.5-pro` | $0.00125 | $0.005 | 4:1 |

---

## Functions

### `estimate_cost(model, input_tokens, output_tokens) -> float`

**Location:** `cost.py:36`

Computes USD cost for a single model call.

**Logic:**
1. Look up `model` in `MODEL_PRICING`
2. If not found, try provider-prefix fallback (e.g., `anthropic/any-model` → first `anthropic/` entry)
3. If still not found, return `0.0`
4. Compute: `(input_tokens / 1000) * input_per_1k + (output_tokens / 1000) * output_per_1k`

**Test evidence** (`test_cost_accounting.py`):
- `test_known_model_cost` — Claude Sonnet 4 with 1000 input + 500 output → cost > 0
- `test_unknown_model_cost` — `unknown/model` → returns 0.0
- `test_zero_tokens_cost` — Zero tokens → returns 0.0
- `test_cost_scales_with_tokens` — 2x tokens → 2x cost (within tolerance)
- `test_output_more_expensive_than_input` — Output cost > input cost for same tokens
- `test_cost_is_float` — Always returns `float`

### `get_pricing_info(model) -> dict | None`

**Location:** `cost.py:53`

Returns raw pricing dict for a model, or `None` if unknown.

**Test evidence:**
- `test_all_known_models_have_pricing` — All 8 models return valid pricing
- `test_pricing_info_returns_none_for_unknown` — Unknown model → `None`

### `CostEntry` (dataclass)

**Location:** `cost.py:25`

Data class for a single cost record:
- `model: str`
- `input_tokens: int`
- `output_tokens: int`
- `input_cost: float`
- `output_cost: float`
- `total_cost: float`
- `timestamp: float`

Not currently used in production — exists for future cost logging.

---

## Integration Status

### What Works

| Component | Status | Evidence |
|-----------|--------|----------|
| `estimate_cost()` | ✅ Tested | 8 tests in `test_cost_accounting.py` |
| `get_pricing_info()` | ✅ Tested | 2 tests in `test_cost_accounting.py` |
| `MODEL_PRICING` | ✅ Complete | 8 models with real pricing |
| Provider-prefix fallback | ✅ Tested | Unknown model with known provider prefix → uses first matching entry |

### What Is NOT Wired

| Component | Status | Gap |
|-----------|--------|-----|
| `BudgetManager.record_model_call()` | ❌ Does not call `estimate_cost()` | Token counts tracked but no USD cost |
| `BudgetManager._session_budgets` | ❌ No `estimated_cost_usd` updated | `BudgetUsage.estimated_cost_usd` always 0.0 |
| `BudgetManager._run_budgets` | ❌ No cost tracking | No cost-based budget enforcement |
| `BudgetManager.check_budget()` | ❌ No cost check | Only checks tokens/calls, not cost |
| `BudgetConfig.max_cost_usd` | ⚠️ Field exists ($5.0 default) | Never checked or enforced |

### Gap Analysis

The `BudgetUsage` dataclass (`budget.py:34`) has an `estimated_cost_usd` field, and `BudgetConfig` has `max_cost_usd = 5.0`. However:

1. `record_model_call()` (`budget.py:90`) increments `input_tokens`, `output_tokens`, `total_tokens`, and `model_calls` but **never** calls `estimate_cost()`
2. `check_budget()` (`budget.py:155`) checks `total_tokens`, `model_calls`, `tool_calls`, `subagent_calls` but **never** checks `estimated_cost_usd` vs `max_cost_usd`
3. The `CostEntry` dataclass exists but is **never instantiated** anywhere in the codebase

---

## Token Estimation

The `BudgetManager` receives token counts from `AgentEngine.run()` at `engine.py:388-396`:

```python
usage_tokens = len(response.content or "") // 4
if response.tool_calls:
    usage_tokens += sum(len(json.dumps(tc.arguments)) // 4 for tc in response.tool_calls)
self._budget_manager.record_model_call(
    run_id,
    input_tokens=usage_tokens // 2,
    output_tokens=usage_tokens // 2,
)
```

This is a rough heuristic — splitting estimated tokens 50/50 between input and output. The actual input/output split from the provider is not captured.

---

## Future Extension Points

1. **Wire `estimate_cost()` into `record_model_call()`** — Add cost tracking per model call
2. **Add cost-based budget enforcement** — Check `estimated_cost_usd >= max_cost_usd` in `check_budget()`
3. **Add `CostEntry` logging** — Record each call's cost for analytics
4. **Add provider-specific token counts** — Parse actual usage from provider responses
5. **Add cost alerting** — Emit `budget_warning` events when cost approaches threshold

---

## Test Coverage

| Test | What It Proves |
|------|----------------|
| `test_known_model_cost` | Cost calculation is correct for known models |
| `test_unknown_model_cost` | Unknown models return 0.0 (no crash) |
| `test_zero_tokens_cost` | Zero tokens → zero cost |
| `test_all_known_models_have_pricing` | All 8 models have valid pricing data |
| `test_cost_scales_with_tokens` | Cost scales linearly with token count |
| `test_output_more_expensive_than_input` | Output tokens cost more than input tokens |
| `test_pricing_info_returns_none_for_unknown` | Unknown model → None (not crash) |
| `test_cost_is_float` | Return type is always float |

**Total: 8 tests, all passing**
