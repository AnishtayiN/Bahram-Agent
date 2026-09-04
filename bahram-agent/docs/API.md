# API Reference

The public surface you are meant to use. Every snippet here is copied from a
running example; none of it is illustrative-only.

```bash
cd bahram-agent
python -m pytest tests/test_agent_boot.py -q   # these snippets, executed
```

---

## `Agent`

`bahram/core/agent.py`

```python
import asyncio

from bahram.core.agent import Agent
from bahram.core.config import Config

config = Config()                       # or Config.from_file("config/config.yaml")
config.memory.database = ":memory:"     # keep the run off the filesystem

agent = Agent(config=config)            # also: Agent(config_path="config/config.yaml")

async def main():
    await agent.start()                 # registers tools, memory, skills, autonomy
    response = await agent.run("Summarise this repository", model="fake/model")
    print(response.content)
    await agent.stop()

asyncio.run(main())
```

`Agent(config=...)` takes precedence over `Agent(config_path=...)`; with
neither, it loads `config/config.yaml` (absent file → defaults).

### Methods

| Method | Returns | Notes |
|---|---|---|
| `await start()` | `None` | registers the 11 default tools, memory, the 3 bundled skills and the autonomy layer |
| `await stop()` | `None` | idempotent |
| `await run(message, session_id=None, model=None, messages=None, use_planning=False)` | `AgentResponse` | the full tool loop |
| `await chat(message, session_id=None, model=None)` | `AgentResponse` | `run` with `use_planning=False` |
| `await run_with_plan(message, session_id=None, model=None)` | `AgentResponse` | plans first; `response.metadata` carries `plan_id` and `plan_status` |
| `async for chunk in agent.chat_streaming(message, session_id=None, model=None)` | `str` | one streaming turn |
| `create_session(metadata=None)` / `get_session(id)` / `delete_session(id)` | `Session` | sessions are also persisted in SQLite |
| `get_history(session_id)` / `clear_history(session_id)` | `list[Message]` | |
| `await execute_command(tool_name, **kwargs)` | `dict` | invoke a registered tool directly; returns `{"content", "success", "error"}` |
| `await delegate_to_subagent(objective, allowed_tools=None, model=None)` | result | sub-agent with a restricted tool allow-list |
| `await create_background_job(job_type, session_id, payload=None)` | job | |
| `checkpoint_run(run_id, plan)` | checkpoint | crash recovery |
| `await analyze_and_learn(run_id, goal, trajectory_steps, tool_results, success)` | `dict` | lesson extraction and skill promotion |

`register_provider`, `register_tool`, `get_provider` and friends live on
`agent.engine` (`bahram/core/engine.py`).

---

## `Config`

`bahram/core/config.py` — nested dataclasses, **not** flat keyword arguments.
The `Config(model=..., provider=...)` form shown in older revisions of this
file never worked.

```python
from bahram.core.config import Config

config = Config()
config.agent.model = "anthropic/claude-sonnet-4-20250514"
config.agent.max_iterations = 15
config.memory.database = ":memory:"
config.tools.disabled = ["container"]
config.security.require_approval = ["bash", "write", "edit"]

config.providers["anthropic"] = ProviderConfig(api_key="…", enabled=True)
```

Loading from YAML merges over the defaults — only the keys you write change:

```yaml
# config/config.yaml
agent:
  name: Bahram
  model: anthropic/claude-sonnet-4-20250514
  max_iterations: 15
memory:
  database: data/memory.db
  max_context_turns: 20
providers:
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}   # ${VAR} is expanded from the environment
    enabled: true
```

`Config.from_file(path)` returns defaults when the file is missing, warns and
returns defaults when it is unparseable, and **ignores unknown keys with a
warning** naming the section — one typo costs one setting, not start-up.

Sections: `agent`, `providers`, `memory`, `skills`, `tools`, `platforms`,
`scheduler`, `security`, `logging`, `server`.

---

## `AgentResponse`, `Message`, `ToolCall`

`bahram/core/engine.py`

```python
response = await agent.run("hi", model="fake/model")

response.content          # str
response.state            # RunState: COMPLETED | FAILED | CANCELLED | TIMEOUT
response.tool_calls       # list[ToolCall]
response.metadata         # dict
```

Writing a provider of your own means implementing two methods — see
`tests/test_agent_boot.py::ScriptedProvider` for a working example:

```python
class MyProvider:
    async def complete(self, messages, tools=None) -> AgentResponse: ...
    def stream(self, messages, tools=None) -> AsyncIterator[str]: ...   # async generator

agent.engine.register_provider("mine", MyProvider())
response = await agent.run("hi", model="mine/model-1")
```

`stream` is declared as a plain `def` returning `AsyncIterator[str]`: every
implementation is an async generator, and callers iterate it with
`async for` rather than awaiting it.

---

## Tools

A tool is any object exposing `name`, `description`, `parameters`, `schema()`
and `async execute(**kwargs)`. `BaseTool` (`bahram/tools/base.py`) provides
the first four as properties and leaves `execute` to the subclass.

```python
from bahram.tools.base import BaseTool

class WeatherTool(BaseTool):
    @property
    def name(self) -> str:
        return "weather"

    @property
    def description(self) -> str:
        return "Current weather for a city."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        }

    async def execute(self, **kwargs) -> str:
        return f"It is sunny in {kwargs['city']}"

agent.engine.register_tool("weather", WeatherTool())
```

Every call then passes through the engine's approval gate automatically. The
11 tools registered by default are listed in `docs/FEATURE_MATRIX.md`.

---

## Skills

`bahram/skills/manager.py` — three skills ship in `skills/`
(`code-review`, `deploy`, `research`) and load on `start()`. A skill is a
Python module with `SKILL_NAME`, `SKILL_DESCRIPTION` and `SKILL_TRIGGERS`
plus a `run(**kwargs)` coroutine; `SkillManager.find_skill()` is a coroutine
and must be awaited.

## MCP

`bahram/mcp/client.py` — see `tests/test_mcp_integration.py` for a complete
stdio server and the `Agent` wiring. Configure with
`config.mcp.servers = [{"name": …, "type": "stdio", "command": [...]}]`;
each discovered tool is registered as `mcp_<tool-name>`.
