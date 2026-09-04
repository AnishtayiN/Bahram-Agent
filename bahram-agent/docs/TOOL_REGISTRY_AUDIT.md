# Tool Registry Audit

What is actually registered, where it comes from, and what guards it.

Regenerate with:

```bash
cd bahram-agent
python - <<'PY'
import asyncio
from bahram.core.agent import Agent
from bahram.core.config import Config

async def main():
    c = Config(); c.memory.database = ":memory:"
    a = Agent(config=c); await a.start()
    for n, t in sorted(a.engine.tools.items()):
        print(f"{n:15s} {type(t).__module__}.{type(t).__name__}")
asyncio.run(main())
PY
```

---

## Registration path

`bahram/tools/__init__.py`

```
init_tools(engine, config, strict=False)
  → _disabled_names(config)        # config.tools.disabled
  → _build_core_tools(tools_config)
      → engine.register_tool(name, tool)   for each of the 11
  → verify every DEFAULT_TOOL_NAMES entry is present or explicitly disabled
```

* Called from `Agent._init_tools()` during `await agent.start()`.
* `DEFAULT_TOOL_NAMES` is the contract; if a name is missing after
  registration and was not disabled, `init_tools` raises `ToolLoadError`.
* `strict=True` turns a single failing tool into an exception instead of a
  logged error and a partial registry.
* Tool modules are imported lazily inside `_build_core_tools`, so a broken
  optional dependency in one module cannot stop the package importing.

---

## Registered by default — 11 tools

| # | Name | Class | Module | Schema | Guards reached from the tool |
|---|------|-------|--------|--------|------------------------------|
| 1 | `bash` | `BashTool` | `bahram/tools/bash.py` | ✅ | `TirithScanner`, `SupplyChainGuard` |
| 2 | `read` | `ReadTool` | `bahram/tools/file.py` | ✅ | `FileWriteSafety` |
| 3 | `write` | `WriteTool` | `bahram/tools/file.py` | ✅ | `FileWriteSafety` |
| 4 | `edit` | `EditTool` | `bahram/tools/file.py` | ✅ | `FileWriteSafety` |
| 5 | `webfetch` | `WebFetchTool` | `bahram/tools/web.py` | ✅ | `WebsitePolicy`, `SSRFProtector` |
| 6 | `websearch` | `WebSearchTool` | `bahram/tools/web.py` | ✅ | `WebsitePolicy`, `SSRFProtector` |
| 7 | `execute_code` | `ExecuteCodeTool` | `bahram/tools/execute_code.py` | ✅ | sandboxed subprocess |
| 8 | `git` | `GitTool` | `bahram/tools/extended.py` | ✅ | `asyncio.create_subprocess_exec` (argv, no shell) |
| 9 | `process_list` | `ProcessListTool` | `bahram/tools/extended.py` | ✅ | `ps` via subprocess |
| 10 | `container` | `ContainerTool` | `bahram/tools/extended.py` | ✅ | `docker` via subprocess |
| 11 | `document_read` | `DocumentReadTool` | `bahram/tools/extended.py` | ✅ | file read |

**Every one of these additionally passes through `ApprovalSystem` in
`ToolExecutor._execute_once`**, which renders the call to a command string and
applies the 39 dangerous patterns and 6 hardline patterns. That gate is what
makes "gated" true for tools that have no guard of their own.

Registration order is the `_build_core_tools` order above:
`bash, read, write, edit, webfetch, websearch, execute_code, git,
process_list, container, document_read`.

---

## Tool interface vs. classes that merely have an `execute()`

Only the 11 tools above implement the interface the engine requires —
`name`, `description`, `parameters` and `schema()` alongside
`async execute(**kwargs)`.

Two more modules define a class with an `execute()` method but **without**
`name` / `parameters` / `schema()`, so they cannot be handed to
`engine.register_tool` as they stand:

| Class | Module | `execute()` signature | Notes |
|---|---|---|---|
| `DatabaseTool` | `bahram/tools/database.py` | `execute(query, params=None)` | SQL access; a library class, not an engine tool |
| `TerminalTool` | `bahram/tools/terminal.py` | `async execute(command, …)` | persistent PTY session; the `os.fork()` path is exercised in a child interpreter by `tests/test_tools_capability_d.py` |

An earlier draft of this file described both as "opt-in tools". That was
wrong — `hasattr(DatabaseTool, "name")` is `False`. They are useful library
code and they are tested, but wiring them as agent tools needs an adapter.

---

## The other tool modules

`bahram/tools/` contains 50 modules. 39 of them are **not** agent tools: they
expose domain methods rather than the `execute()` tool interface, and are not
registered by anything. Examples — `ImageGenTool.generate()`,
`SmartDocGenerator`, `SecurityScanner`, `Profiler`, `PerformanceMonitor`,
`MigrationTool`, `LSPTool`, `RefactorTool`, `TaskTool`, `TodoTool`.

They are covered by tests where they are covered
(`tests/test_tools_capability_c.py`, `tests/test_tools_capability_d.py`) and
are available as library code, but nothing in `bahram/` instantiates them.
Listing them as "40+ tools" was wrong; this is the corrected count.

---

## Duplicate `git` module

`bahram/tools/git.py` defines its own `GitTool`, and so does
`bahram/tools/extended.py`. The registered one is **extended.py's**;
`tools/git.py` is not imported by `init_tools`. Both are tested. Flagged here
as a known wart rather than resolved, because deleting either one is a
behaviour change for whoever imports it directly.

---

## MCP tools

Tools discovered from a configured MCP server are registered as
`mcp_<tool-name>` after the defaults, during `Agent._init_mcp_tools()`. They
are plain adapters over `MCPClient.call_tool`, so they inherit the engine's
approval gate. See `tests/test_mcp_integration.py`.
