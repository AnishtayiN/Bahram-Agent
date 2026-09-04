# Changelog

All notable changes to Bahram Agent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Note on the historical entries.** Everything below `## [1.0.0]` predates
> this remediation pass and was written without verification. Several of its
> claims describe features that were never wired to anything — "40+ built-in
> tools", "plugin system", "voice support", "cron scheduler", "dashboard" — and
> those modules have since been deleted because nothing imported them. Treat
> the older sections as unreliable; `docs/FEATURE_MATRIX.md` is the
> authoritative description of what runs today.

## [Unreleased]

### Fixed

Every item below is a defect that was found by driving the real code, not by
reading it. Each was committed separately; the commit message carries the
evidence.

- **`Agent.run` was unusable.**
  `BudgetManager.record_tool_call()` rejected the `tool_name` keyword the
  engine passes, so *every* run that invoked a tool crashed with
  `TypeError: ... unexpected keyword argument 'tool_name'`.
  `Agent._retrieve_skills()` called the coroutine `SkillManager.find_skill()`
  without awaiting it, so skill context was always empty.
  `AgentEngine.run_streaming` looped `max_iterations` (15) times over a
  streaming protocol that carries no tool calls, so a streaming chat called
  the provider 15 times and concatenated every reply.
- **The in-memory mode wrote to disk.** `memory.database: ":memory:"` did not
  stop the autonomy subsystems, the trajectory recorder or the session store
  from creating `data/…`. They now accept `data_dir=None` and `Agent`
  propagates it, so an ephemeral run touches no files at all.
- **The MCP integration never registered a tool.** `Agent._init_mcp_tools`
  passed a config dict to `MCPClient.connect()` (which takes a server name),
  awaited the synchronous `list_tools()`, and called `.get()` on the strings it
  returned. All three errors were swallowed by a broad `except`.
- **Five security guard bypasses.**
  `SSRFProtector` only inspected dotted-quad literals, so `localhost`,
  `http://2130706433/`, `http://0x7f000001/` and `[::ffff:127.0.0.1]` all
  passed; hosts are now resolved and every address classified.
  `PromptInjectionDetector` missed "disregard the previous prompt", and its
  three invisible-Unicode patterns matched a literal `\u200b` because of a
  doubled backslash. `FileWriteSafety` caught `..` but not symlinks, and
  protected individual files instead of directories, so
  `/etc/cron.d/payload` was writable. `SecurityKernel` treated a capability
  with `expires_at=0` as "never expires". `tools/bash.py` imported a
  `SupplyChainGuard` class that `bahram/security/supply_chain.py` never
  defined — the `ImportError` was swallowed and bash ran with no supply-chain
  guard at all.
- **Skills never loaded.** `SkillManager._load_skill` awaited
  `spec.loader.exec_module()`, which is synchronous and returns `None`, so
  every `skills/*.py` failed with "object NoneType can't be used in 'await'
  expression" and the agent ran with an empty skill set.
- **Auto-learning never ran.** `Agent.run_with_plan` read `step.step_id`, but
  `PlanStep` has `id`; the resulting `AttributeError` was swallowed by
  `except Exception: logger.warning("Auto-learning failed")`.
- **`GatewayService.get_status()` raised `AttributeError`** on macOS: it
  called `self._launchctl_list()`, a method that does not exist.
- **One stray key in `config.yaml` aborted start-up** with
  `TypeError: AgentConfig.__init__() got an unexpected keyword argument`.
  Unknown keys are now ignored with a warning naming the section and keys.
- **`SecretsManager.import_from_env(prefix=…)` imported nothing**: the
  "looks like a secret" name filter ran on the full variable name, so
  `BAHRAM_API_KEY` never matched `API_`. It now runs on the name after the
  prefix is stripped.
- **Zombie processes.** Four tools killed a timed-out child without reaping
  it; they now `await proc.wait()`.
- **`tools/git.py` built shell strings**, which lost `git log --format=%s`,
  broke `git branch --format=%(refname:short)` with
  `Syntax error: "(" unexpected`, and interpolated the commit message into a
  shell command. It uses `create_subprocess_exec` with an argv list now.

### Added

- `bahram/security/redaction.py` — scrubs provider keys, JWTs, bearer
  tokens, PEM blocks, URL credentials and `key=value` assignments from every
  log record, installed by `Agent._setup_logging`, plus
  `SecretsManager.redact()`.
- `bahram/security/supply_chain.py::SupplyChainGuard` — refuses dependency
  confusion (non-public `--index-url` / `--registry`), disabled package
  verification and unverified remote install scripts.
- Tests: `tests/test_agent_boot.py` (real `Agent`, real tools, offline
  end-to-end through a scripted provider), `tests/test_security_hardening.py`
  (182 attack/assert pairs), `tests/test_memory_backends.py`,
  `tests/test_mcp_integration.py` (a real MCP server as a child process),
  `tests/test_core_services.py`, `tests/test_tools_capability_c.py`,
  `tests/test_tools_capability_d.py`.
- `.github/workflows/ci.yml` — ruff + mypy, pytest on 3.10/3.11/3.12 with
  `--cov-fail-under=75`, and a wheel build/import/`bahram --help` smoke test.

### Changed

- Coverage rose from 54.4 % to 80.8 % overall; core 89.3 %, security 97.7 %,
  memory 95.1 %, autonomy 85.2 %, tools 85.3 %.
- `mypy bahram/core bahram/security` went from 40 errors to 0.
- `LLMProvider.stream` is declared `def stream(...) -> AsyncIterator[str]`
  rather than `async def`, because every implementation is an async generator
  and callers iterate it with `async for`.

### Removed

- 45 modules that no other module imported and no test referenced: the
  dashboard, scheduler, plugin system, skill hub and bundles, voice, MoA,
  journey, workflow, observability-facing duplicates, the external memory
  providers (Honcho, nudge, session search), DM pairing, and a root-level
  `cli.py` that duplicated `bahram/cli.py` (which is what `[project.scripts]`
  resolves).
- `sentence-transformers` and `numpy` from the runtime dependencies — memory
  search is SQLite FTS5 and neither was imported anywhere.
- `data/sessions.db` from version control (empty, regenerable, and `data/` is
  git-ignored).

---

# Changelog

All notable changes to Bahram Agent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).



### Added
- **Agent State Machine**: 13 states (CREATED → COMPLETED/FAILED/CANCELLED/TIMEOUT)
- **Cancellation Support**: asyncio.Event-based cancellation at every iteration
- **Config-Driven Limits**: max_iterations, max_runtime_seconds, max_tool_calls
- **ToolExecutor**: Mediated tool execution with security pipeline
- **Extended Tools**: git, process_list, container, document_read
- **SQLite Memory**: FTS5 full-text search with LIKE fallback
- **Trajectory Persistence**: Runs, steps, tool_calls, events tables
- **Red Team Tests**: 19 security tests (command injection, SSRF, file safety)
- **Chaos Tests**: Timeouts, corruption, concurrency, error handling
- **Benchmark Suite**: E2E tests for conversation, tools, state, memory
- **Documentation**: Feature matrix, security model

### Changed
- **Engine Rewrite**: Proper state machine with explicit transitions
- **Tool Pipeline**: All tools go through ToolExecutor with security checks
- **Memory System**: JSON files → SQLite with FTS5 indexing
- **Persistence Layer**: sessions + messages → runs, steps, tool_calls, events
- **Security Integration**: file_safety, website_policy, SSRF, tirith, supply_chain all wired

### Fixed
- Tool execution no longer crashes agent on failure
- Proper timeout handling at tool and run level
- Security checks applied consistently across all tools

## [1.0.0] - 2024-01-01

### Added
- Core agent system
- 17+ LLM providers (Anthropic, OpenAI, Groq, Mistral, Google, etc.)
- 40+ built-in tools
- Multi-platform support (Telegram, Discord, Slack, WhatsApp, Signal)
- Memory system (conversation, episodic, semantic)
- Security features (command approval, SSRF protection, file safety)
- Skill system with bundles
- MCP client and server
- Plugin system
- Voice support (transcription and TTS)
- Cron scheduler
- Dashboard and monitoring
- Session resume
- Profile management
- Secrets management

### Changed
- Improved error handling
- Better context management
- Enhanced security scanning

### Fixed
- Memory leaks in conversation handler
- Platform connection stability
- Token counting accuracy

## [0.9.0] - 2023-12-01

### Added
- Beta release
- Basic provider support
- Core tools
- Telegram integration

## [0.8.0] - 2023-11-01

### Added
- Initial development
- Core architecture
- Provider framework
