# Cost Model

How Bahram accounts for money while a run is in flight, and what is actually
enforced.

> The previous version of this document said the cost module was "not wired
> into BudgetManager". That is no longer true — and checking it took one grep:
> `bahram/autonomy/budget.py` imports `estimate_cost` and calls it in
> `record_model_call`. Treat this file as the current description; verify any
> claim in it against the source before relying on it.

---

## Where cost lives

| Piece | Location |
|---|---|
| Static price table | `bahram/autonomy/cost.py` → `MODEL_PRICING` |
| Per-call estimator | `estimate_cost(model, input_tokens, output_tokens) -> float` |
| Price lookup | `get_pricing_info(model) -> dict \| None` |
| Accumulation | `BudgetManager.record_model_call()` (`bahram/autonomy/budget.py`) |
| Enforcement | `BudgetManager.check_budget()` and `BudgetManager.check_cost_budget()` |
| Ceiling | `BudgetConfig.max_cost_usd` |

## The price table

`MODEL_PRICING` in `bahram/autonomy/cost.py` — USD per 1 000 tokens:

| Model | Input | Output |
|---|---|---|
| `anthropic/claude-sonnet-4-20250514` | $0.003 | $0.015 |
| `anthropic/claude-3-5-sonnet-20241022` | $0.003 | $0.015 |
| `anthropic/claude-3-haiku-20240307` | $0.00025 | $0.00125 |
| `openai/gpt-4o` | $0.0025 | $0.01 |
| `openai/gpt-4o-mini` | $0.00015 | $0.0006 |
| `openai/gpt-3.5-turbo` | $0.0005 | $0.0015 |
| `google/gemini-2.0-flash` | $0.000075 | $0.0003 |
| `google/gemini-1.5-pro` | $0.00125 | $0.005 |

These are hardcoded and go stale. They are a planning aid, not an invoice.
A model that is not in the table resolves by provider prefix
(`anthropic/some-new-model` → the first `anthropic/` entry) and, failing that,
estimates at **$0.00** — which means an unrecognised model is treated as free
and no budget ceiling will trip. If you run a model that is not listed, add it.

## What is wired

1. `AgentEngine.run()` records a model call after every provider response:
   ```python
   self._budget_manager.record_model_call(
       run_id,
       input_tokens=usage_tokens // 2,
       output_tokens=usage_tokens // 2,
       model=model,
   )
   ```
2. `record_model_call()` calls `estimate_cost(model, input, output)` and adds
   the result to `run_budget.estimated_cost_usd` (and the session budget when
   a `session_id` is supplied).
3. `check_budget()` appends `"cost_usd"` to `exceeded` when
   `estimated_cost_usd >= max_cost_usd`, which stops the run with
   `RunState.COMPLETED` and the message
   `Budget limit reached: Budget limit exceeded: cost_usd`.
4. `check_cost_budget(run_id)` reports `cost_usd`, `limit`, `soft_exceeded`
   and `hard_exceeded` against a soft (warning) and hard (stop) threshold.

## What is approximate

The token counts are **estimated, not reported by the provider**:

```python
usage_tokens = len(response.content or "") // 4
if response.tool_calls:
    usage_tokens += sum(len(json.dumps(tc.arguments)) // 4 for tc in response.tool_calls)
```

`// 4` is the usual "about four characters per token" rule of thumb, and the
total is then split 50/50 between input and output because the engine does not
read `usage` from the provider response. Real usage can differ from the
estimate by a wide margin for non-English text, code, or base64 payloads.
Treat `estimated_cost_usd` as a circuit breaker, not as billing.

## What is not done

* `CostEntry` (`bahram/autonomy/cost.py`) is a dataclass for a per-call record
  that nothing instantiates. There is no cost history, no export, no
  per-provider rollup.
* Provider-reported token counts are not parsed, so the numbers above cannot
  be reconciled against a vendor invoice.
* There is no daily/monthly ceiling — `max_cost_usd` is per run.

## Verifying this document

```bash
cd bahram-agent
grep -n "estimate_cost" bahram/autonomy/budget.py        # accumulation
grep -n "max_cost_usd"  bahram/autonomy/budget.py        # enforcement
python -m pytest tests/test_autonomy.py -q -k cost        # behaviour
```
