# Bahram Agent

Bahram is a self-improving AI agent framework: a planning/execution engine, a
tool registry with a security pipeline in front of it, SQLite-backed memory,
and an autonomy layer that plans, verifies, recovers and learns.

This is the package README. The short version is below; the verified detail
lives in the sibling documents.

| Document | Contents |
|---|---|
| `FEATURE_MATRIX.md` | every capability, whether it is wired, and the test that proves it |
| `SECURITY_MODEL.md` | the guards, what each one stops, and the known limitations |
| `TOOL_REGISTRY_AUDIT.md` | the 11 registered tools, the 39 helper modules, and the difference |
| `API.md` | the public Python surface, with snippets that run |
| `AUTONOMY.md` | the plan → execute → verify → replan → recover → learn loop |
| `COST_MODEL.md` | how spend is estimated and what is actually enforced |
| `ENGINEERING_REPORT.md` | the remediation record, with the commands and numbers |

## Install

```bash
pip install -e .          # from bahram-agent/
pip install -e ".[dev]"   # + pytest, ruff, mypy
pip install -e ".[telegram]"   # optional platform
```

## Use

```python
import asyncio

from bahram.core.agent import Agent
from bahram.core.config import Config

config = Config()
config.memory.database = ":memory:"          # keep the run off the filesystem
config.providers["anthropic"].api_key = "…"  # or set ANTHROPIC_API_KEY

async def main():
    agent = Agent(config=config)
    await agent.start()
    response = await agent.run("Summarise this repository")
    print(response.content)
    await agent.stop()

asyncio.run(main())
```

`Config(model=..., provider=...)` — the flat form that older drafts of these
docs showed — never worked. Config is nested dataclasses; see `API.md`.

## What is registered by default

11 tools: `bash`, `read`, `write`, `edit`, `webfetch`, `websearch`,
`execute_code`, `git`, `process_list`, `container`, `document_read`.

17 providers in `PROVIDER_MAP`: anthropic, openai, google, groq, mistral,
deepseek, kimi, minimax, nous, nvidia, ollama, lmstudio, openrouter,
huggingface, xiaomi, zhipu, custom.

3 bundled skills: `code-review`, `deploy`, `research`.

## Verify

```bash
cd bahram-agent
python -m pytest tests/ -q                       # the suite
python -m pytest tests/ -q --cov=bahram --cov-fail-under=75
ruff check bahram tests scripts                  # 0 errors
ruff format --check bahram tests scripts         # clean
mypy bahram/core bahram/security                 # clean
```

## Status

The suite passes, coverage is above the 75 % gate (and above 85 % for core,
security, memory, autonomy and tools), and lint and type checks are clean.
Two modules — `bahram/security/kernel.py` and `bahram/autonomy/tool_gateway.py`
— are implemented and unit-tested but not constructed by anything in
`bahram/`; both are marked as such in `FEATURE_MATRIX.md` rather than counted
as features.
