# Cost Report — Cost Accounting System

## Pricing Source

Hardcoded in `bahram/autonomy/cost.py:13-22` — `MODEL_PRICING` dict.

| Model | Input (per 1K tokens) | Output (per 1K tokens) | Source |
|-------|----------------------|------------------------|--------|
| `anthropic/claude-sonnet-4-20250514` | $0.003 | $0.015 | Anthropic pricing page |
| `anthropic/claude-3-5-sonnet-20241022` | $0.003 | $0.015 | Anthropic pricing page |
| `anthropic/claude-3-haiku-20240307` | $0.00025 | $0.00125 | Anthropic pricing page |
| `openai/gpt-4o` | $0.0025 | $0.01 | OpenAI pricing page |
| `openai/gpt-4o-mini` | $0.00015 | $0.0006 | OpenAI pricing page |
| `openai/gpt-3.5-turbo` | $0.0005 | $0.0015 | OpenAI pricing page |
| `google/gemini-2.0-flash` | $0.000075 | $0.0003 | Google pricing page |
| `google/gemini-1.5-pro` | $0.00125 | $0.005 | Google pricing page |

**Last verified:** Phase 11 (hardcoded, not dynamically fetched).

---

## Token Accounting

### How Tokens Are Counted

`engine.py:395-401`:
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

**Method:** Character count divided by 4 (rough heuristic). Split 50/50 between input and output.

**Accuracy:** Low. Real tokenization varies by model (3-5 chars/token typically). The 50/50 input/output split is arbitrary.

### What's Actually Tracked

| Metric | Tracked | Source |
|--------|---------|--------|
| Total tokens | Yes | `len/4` heuristic |
| Input tokens | Yes | `total / 2` |
| Output tokens | Yes | `total / 2` |
| Model calls | Yes | Incremented per call |
| Tool calls | Yes | Incremented per call |
| Subagent calls | Yes | Incremented per call |
| Cost (USD) | Yes | `estimate_cost()` with hardcoded prices |

---

## Calculation Method

### Cost Formula

```
cost = (input_tokens / 1000) * input_per_1k + (output_tokens / 1000) * output_per_1k
```

### Example

Claude Sonnet 4 with 1000 input tokens and 500 output tokens:
```
cost = (1000/1000) * 0.003 + (500/1000) * 0.015
     = 0.003 + 0.0075
     = $0.0105
```

---

## Unknown Price Behavior

When a model is not in `MODEL_PRICING`:

1. Try provider-prefix fallback: `anthropic/any-model` → first `anthropic/` entry
2. If still not found, return `0.0`

**Risk:** Unknown models report $0 cost. Budget enforcement based on cost will not trigger.

**Mitigation:** Token-based budgets still work (`max_total_tokens`, `max_model_calls`).

---

## Budgets

### Default Limits

| Limit | Default | Enforced |
|-------|---------|----------|
| `max_input_tokens` | 100,000 | Yes (in `check_budget()`) |
| `max_output_tokens` | 50,000 | No (not checked separately) |
| `max_total_tokens` | 150,000 | Yes |
| `max_cost_usd` | $5.00 | Yes |
| `max_model_calls` | 50 | Yes |
| `max_tool_calls` | 100 | Yes |
| `max_subagent_calls` | 10 | Yes |
| `warning_threshold` | 0.8 (80%) | Yes |

### Warning System

Warnings emitted when usage reaches 80% of limit:
- Token usage warning
- Model calls warning
- Cost warning (per run and per session)

### Budget Check Flow

1. `engine.py:358-368` — Check budget before each iteration
2. `budget.py:178-198` — `check_budget()` returns exceeded list
3. If any limit exceeded, engine returns with "Budget limit reached" message
4. `budget.py:200-228` — `check_cost_budget()` provides detailed cost status with soft/hard limits

---

## Warnings

### Current Warnings

| Warning | Trigger | Action |
|---------|---------|--------|
| Session token usage | ≥ 80% of max_total_tokens | Logged + event emitted |
| Run token usage | ≥ 80% of max_total_tokens | Logged + event emitted |
| Run model calls | ≥ 80% of max_model_calls | Logged + event emitted |
| Run cost | ≥ 80% of max_cost_usd | Logged + event emitted |
| Session cost | ≥ 80% of max_cost_usd | Logged + event emitted |
| Context window low | < 500 tokens remaining | Logged + event emitted |

### What's NOT Warned

| Gap | Risk |
|-----|------|
| No per-tool cost tracking | Cannot identify expensive tools |
| No per-step cost tracking | Cannot identify expensive plan steps |
| No cost alerting to user | User not notified of approaching limits |
| No cost trend analysis | Cannot predict future costs |
| No cost cap per session | Session cost can exceed run cost |

---

## Test Coverage

| Test | What It Proves |
|------|----------------|
| `test_known_model_cost` | Cost calculation correct for known models |
| `test_unknown_model_cost` | Unknown models return 0.0 |
| `test_zero_tokens_cost` | Zero tokens → zero cost |
| `test_all_known_models_have_pricing` | All 8 models have valid pricing |
| `test_cost_scales_with_tokens` | Cost scales linearly |
| `test_output_more_expensive_than_input` | Output tokens cost more |
| `test_pricing_info_returns_none_for_unknown` | Unknown model → None |
| `test_cost_is_float` | Return type always float |

**Total: 8 tests, all passing**

---

## Cost Summary

| Category | Status | Notes |
|----------|--------|-------|
| Pricing data | COMPLETE | 8 models with real prices |
| Cost calculation | WORKING | Formula correct |
| Budget integration | WORKING | Cost checked in `check_budget()` |
| Token estimation | HEURISTIC | `len/4` is fast but inaccurate |
| Unknown model handling | SAFE | Returns 0.0, token budgets still work |
| Cost alerting | PARTIAL | Warnings logged but not sent to user |
| Cost analytics | MISSING | No cost trend analysis |
