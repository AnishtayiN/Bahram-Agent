# Bahram Agent ☤

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/python-3.10+-yellow" alt="Python">
</p>

## درباره بهرام / About Bahram

**بَهرام** (Bahram) نامی از اساطیر و تاریخ ایران باستان است؛ نماد **شجاعت، قدرت و پیروزی**.
Bahram is a name from ancient Persian history and myth — it stands for courage,
strength and victory. The agent is named after it; it is inspired by
[Hermes Agent](https://github.com/NousResearch/hermes-agent) from Nous Research
but is an independent implementation.

> **Read the feature list below as a description of what runs today.** Many
> capabilities that older revisions of this README advertised were never wired
> to anything and have been removed; `bahram-agent/docs/FEATURE_MATRIX.md` is
> the authoritative, test-backed list.

---

## What actually ships

| | |
|---|---|
| **11 tools** | `bash`, `read`, `write`, `edit`, `webfetch`, `websearch`, `execute_code`, `git`, `process_list`, `container`, `document_read` |
| **17 providers** | anthropic, openai, google, groq, mistral, deepseek, kimi, minimax, nous, nvidia, ollama, lmstudio, openrouter, huggingface, xiaomi, zhipu, custom |
| **3 skills** | `code-review`, `deploy`, `research` |
| **Memory** | semantic (SQLite FTS5), conversation, episodic, plus pluggable providers |
| **Autonomy** | planner → executor → verifier → replanner → recovery → learning loop, sub-agents, background jobs, budgets |
| **Security** | approval system on every tool call, command scanner, supply-chain guard, SSRF protection, prompt-injection detection, file-write safety, website policy, secret redaction |

Not shipped, despite what older revisions said: no dashboard, no scheduler, no
voice, no plugin system, no skill hub, no external memory providers (Honcho /
Mem0), no WhatsApp / Signal / email / Home Assistant platforms. Those modules
existed but nothing imported them, and they have been deleted. See
`bahram-agent/docs/ENGINEERING_REPORT.md`.

---

## Install

```bash
git clone https://github.com/AnishtayiN/Bahram-Agent.git
cd Bahram-Agent/bahram-agent

pip install -e .                 # runtime only
pip install -e ".[dev]"          # + pytest, ruff, mypy
pip install -e ".[telegram]"     # optional Telegram platform
```

## Quick start

```bash
export ANTHROPIC_API_KEY=sk-…    # or any other supported provider

bahram chat                      # interactive
bahram --help                    # chat | model | skills | serve | gateway | version
```

```python
import asyncio

from bahram.core.agent import Agent
from bahram.core.config import Config

config = Config()
config.memory.database = ":memory:"     # keep the run off the filesystem

async def main():
    agent = Agent(config=config)
    await agent.start()                 # registers the 11 tools, memory and skills
    response = await agent.run("Summarise this repository")
    print(response.content)
    await agent.stop()

asyncio.run(main())
```

`Config(model=..., provider=...)` — the flat form older revisions showed —
never worked. Config is nested dataclasses; see `bahram-agent/docs/API.md`.

## Configuration

`config/config.yaml`, loaded by `Config.from_file`. Unknown keys are ignored
with a warning rather than aborting start-up. `${VAR}` is expanded from the
environment.

```yaml
agent:
  name: Bahram
  model: anthropic/claude-sonnet-4-20250514
  max_iterations: 15
memory:
  database: data/memory.db       # ":memory:" for a fully ephemeral run
  max_context_turns: 20
providers:
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    enabled: true
tools:
  disabled: [container]
security:
  require_approval: [bash, write, edit]
```

## Security

Every tool call passes through `ApprovalSystem` in the engine, on top of the
guard specific to its resource class — Tirith + supply-chain for `bash`,
SSRF + website policy for the web tools, file-write safety for the file tools.
Log records are scrubbed of credentials before a handler sees them.

The complete model, including the parts that are deliberately **not**
mitigated (DNS rebinding), is in `bahram-agent/docs/SECURITY_MODEL.md`.

## Verify

```bash
cd bahram-agent
python -m pytest tests/ -q                              # 1557 passed, 11 skipped
python -m pytest tests/ -q --cov=bahram --cov-fail-under=75
ruff check bahram tests scripts                         # 0 errors
ruff format --check bahram tests scripts                # clean
mypy bahram/core bahram/security                        # clean
```

CI runs all of the above on Python 3.10, 3.11 and 3.12, then builds the wheel
and smoke-tests `import bahram` and `bahram --help` in a clean virtualenv
(`.github/workflows/ci.yml`).

## Documentation

| Document | Contents |
|---|---|
| `bahram-agent/docs/FEATURE_MATRIX.md` | every capability, whether it is wired, and the test that proves it |
| `bahram-agent/docs/SECURITY_MODEL.md` | the guards, what each stops, and known limitations |
| `bahram-agent/docs/API.md` | the public Python surface, with snippets that run |
| `bahram-agent/docs/AUTONOMY.md` | the planning and learning loop |
| `bahram-agent/docs/TOOL_REGISTRY_AUDIT.md` | the 11 tools vs. the 39 helper modules |
| `bahram-agent/docs/COST_MODEL.md` | spend estimation and enforcement |
| `bahram-agent/docs/ENGINEERING_REPORT.md` | the remediation record with commands and numbers |

## License

MIT — see `bahram-agent/LICENSE`.
