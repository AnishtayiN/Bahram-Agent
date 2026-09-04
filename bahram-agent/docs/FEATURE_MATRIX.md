# Bahram Agent — Feature Matrix

Every row below is backed by something that runs. Where a row claims a
behaviour it names the test file that asserts it; where a feature is **not**
wired up, it says so. Nothing here is aspirational.

Regenerate the numbers with:

```bash
cd bahram-agent
python -m pytest tests/ -q --cov=bahram --cov-report=term
ruff check bahram tests scripts
mypy bahram/core bahram/security
```

Last verified: see `docs/ENGINEERING_REPORT.md`.

---

## 1. Runtime

| Capability | Status | Where | Proven by |
|---|---|---|---|
| `Agent` boots and registers all 11 default tools | ✅ | `bahram/core/agent.py` | `tests/test_agent_boot.py::TestAgentBoot` |
| Provider abstraction, 17 providers in `PROVIDER_MAP` | ✅ | `bahram/providers/__init__.py` | `tests/test_agent_boot.py` (empty-key boot registers none) |
| Streaming chat | ✅ | `AgentEngine.run_streaming`, `Agent.chat_streaming` | `tests/test_agent_boot.py::TestAgentStreaming` |
| Cancellation via `asyncio.Event` | ✅ | `AgentEngine.run` | `tests/test_autonomy.py`, `tests/chaos/` |
| Circuit breaker per provider + fallback chain | ✅ | `bahram/providers/fallback.py`, `CircuitBreaker` | `tests/test_core.py`, `tests/phase13/` |
| Budget limits (iterations / runtime / tool calls) | ✅ | `bahram/autonomy/budget.py` | `tests/test_autonomy.py`, `tests/test_agent_boot.py` |
| Trajectory persistence | ✅ | `AgentEngine._persist_trajectory`, `SessionStore.save_trajectory` | `tests/test_core_services.py::TestSessionStore` |
| Fully in-memory mode (`memory.database: ":memory:"`) creates **no** files | ✅ | `Agent.__init__`, all autonomy subsystems take `data_dir=None` | `tests/test_agent_boot.py::test_in_memory_run_creates_no_files` |
| MCP client (stdio + HTTP transports) | ✅ | `bahram/mcp/client.py` | `tests/test_mcp_integration.py` (real child process + real HTTP server) |

### Default tool registry — 11 tools

Produced by booting a real `Agent` and reading `engine.tools`:

| Tool | Class | Module | Guard reached from the tool |
|---|---|---|---|
| `bash` | `BashTool` | `bahram/tools/bash.py` | `TirithScanner`, `SupplyChainGuard` |
| `read` | `ReadTool` | `bahram/tools/file.py` | `FileWriteSafety` |
| `write` | `WriteTool` | `bahram/tools/file.py` | `FileWriteSafety` |
| `edit` | `EditTool` | `bahram/tools/file.py` | `FileWriteSafety` |
| `webfetch` | `WebFetchTool` | `bahram/tools/web.py` | `WebsitePolicy`, `SSRFProtector` |
| `websearch` | `WebSearchTool` | `bahram/tools/web.py` | `WebsitePolicy`, `SSRFProtector` |
| `execute_code` | `ExecuteCodeTool` | `bahram/tools/execute_code.py` | sandboxed subprocess |
| `git` | `GitTool` | `bahram/tools/extended.py` | subprocess (argv, no shell) |
| `process_list` | `ProcessListTool` | `bahram/tools/extended.py` | subprocess |
| `container` | `ContainerTool` | `bahram/tools/extended.py` | subprocess |
| `document_read` | `DocumentReadTool` | `bahram/tools/extended.py` | file read |

`bahram/tools/` ships 50 modules, but only the 11 above implement the tool
interface the engine requires (`name`, `description`, `parameters`,
`schema()`, `async execute(**kwargs)`). Those 11 are what
`bahram/tools/__init__.py:init_tools()` registers, and it honours
`config.tools.disabled`.

The other 39 modules are helper utilities — image generation, LSP, migration,
profiling, refactoring, security scanning, smart completion and doc
generation, task and todo management, terminal and database access. They
expose domain methods such as `ImageGenTool.generate()` or
`DatabaseTool.execute(query)`, and two of them (`DatabaseTool`,
`TerminalTool`) have an `execute()` but no `name`/`parameters`/`schema()`, so
they cannot be registered on the engine without an adapter. They are tested
(`tests/test_tools_capability_c.py`, `tests/test_tools_capability_d.py`) and
usable as library code, but calling the project "40+ tools" was wrong. See
`docs/TOOL_REGISTRY_AUDIT.md`.

---

## 2. Autonomy

| Subsystem | Status | Module | Proven by |
|---|---|---|---|
| Planner | ✅ | `bahram/autonomy/planner.py` | `tests/test_autonomy.py`, `tests/test_agent_boot.py::TestAgentPlanning` |
| Plan executor | ✅ | `bahram/autonomy/executor.py` | `tests/test_autonomy.py` |
| Replanner | ✅ | `bahram/autonomy/replanner.py` | `tests/test_autonomy.py` |
| Verification engine | ✅ | `bahram/autonomy/verification.py` | `tests/test_autonomy.py` |
| Subagent delegation with a tool allow-list | ✅ | `bahram/autonomy/subagent.py` | `tests/redteam/test_redteam.py::TestSubagentEscalation` |
| Background jobs | ✅ | `bahram/autonomy/jobs.py` | `tests/test_autonomy.py`, `tests/test_agent_boot.py` |
| Crash recovery / checkpoints | ✅ | `bahram/autonomy/recovery.py` | `tests/phase11/test_crash_recovery.py` |
| Learning engine + skill lifecycle | ✅ | `bahram/autonomy/learning.py`, `skill_lifecycle.py` | `tests/test_autonomy.py`, `tests/test_agent_boot.py` |
| Event tracker | ✅ | `bahram/autonomy/events.py` | `tests/test_autonomy.py` |
| Budget manager | ✅ | `bahram/autonomy/budget.py` | `tests/test_autonomy.py` |
| Cost accounting | ✅ | `bahram/autonomy/cost.py`, called from `BudgetManager.record_model_call` | `tests/test_autonomy.py`; `docs/COST_MODEL.md` |
| Tool gateway | ⚠️ **not wired** | `bahram/autonomy/tool_gateway.py` | no caller in `bahram/` |

---

## 3. Security

Full model in `docs/SECURITY_MODEL.md`. Summary:

| Guard | Status | Module | Proven by |
|---|---|---|---|
| Command approval (39 patterns + 6 hardline patterns) applied to **every** tool call | ✅ | `bahram/security/approval.py`, `ToolExecutor._execute_once` | `tests/test_security_hardening.py`, `tests/redteam/test_redteam.py` |
| Command scanner (Tirith) on `bash` | ✅ | `bahram/security/tirith.py` | `tests/test_security_hardening.py::TestTirithScanner` |
| Supply-chain guard on install commands | ✅ | `bahram/security/supply_chain.py` | `tests/test_security_hardening.py::TestSupplyChainGuard` |
| SSRF protection with DNS resolution | ✅ | `bahram/security/protection.py` | `tests/test_security_hardening.py::TestSSRFProtector` |
| Prompt-injection detection | ✅ | `bahram/security/protection.py` | `tests/test_security_hardening.py::TestPromptInjectionDetector` |
| File write safety (traversal, symlink, protected dirs, size) | ✅ | `bahram/security/file_safety.py` | `tests/test_security_hardening.py::TestFileWriteSafety` |
| Website policy (allow/deny/log) | ✅ | `bahram/security/website_policy.py` | `tests/test_security_hardening.py::TestWebsitePolicy` |
| Secret redaction in logs | ✅ | `bahram/security/redaction.py` | `tests/test_security_hardening.py::TestRedaction` |
| Encrypted secret store | ✅ | `bahram/core/secrets.py` | `tests/test_core_services.py::TestSecretsManager` |
| Capability kernel | ⚠️ **not wired** | `bahram/security/kernel.py` | `tests/test_security_hardening.py::TestSecurityKernel` (unit only) |

Known limitation, documented rather than hidden: `SSRFProtector` resolves a
host name once. A name that resolves to a public address at check time and to
a private one when the request is made (DNS rebinding) is **not** caught —
closing it requires pinning the resolved address on the socket, which is a
change to how `httpx` is used in `bahram/tools/web.py`. See the docstring on
`SSRFProtector._verdict_for_hostname`.

---

## 4. Memory

| Capability | Status | Module | Proven by |
|---|---|---|---|
| Semantic memory over SQLite FTS5 with LIKE fallback | ✅ | `bahram/memory/semantic.py` | `tests/test_memory_backends.py::TestSemanticMemory` |
| Conversation memory (JSON backing store) | ✅ | `bahram/memory/conversation.py` | `tests/test_memory_backends.py::TestConversationMemory` |
| Episodic memory (tasks, errors, learnings) | ✅ | `bahram/memory/episodic.py` | `tests/test_memory_backends.py::TestEpisodicMemory` |
| Pluggable memory providers | ✅ | `bahram/memory/providers.py` | `tests/test_memory_backends.py::TestMemoryProviders` |
| Session/trajectory persistence | ✅ | `bahram/core/persistence.py` | `tests/test_core_services.py::TestSessionStore` |
| Context window with trimming and summarisation | ✅ | `bahram/core/context.py` | `tests/test_core_services.py::TestContextWindow` |
| Context compression (heuristic + model, with fallback) | ✅ | `bahram/core/compressor.py` | `tests/test_core_services.py::TestContextCompressor` |

---

## 5. Interfaces

| Interface | Status | Entry point | Notes |
|---|---|---|---|
| CLI (`bahram …`) | ✅ | `bahram/cli.py` — `[project.scripts] bahram = "bahram.cli:app"` | commands: `chat`, `model`, `skills`, `serve`, `gateway`, `version`; CI runs `bahram --help` |
| Python API | ✅ | `from bahram.core.agent import Agent` | see `docs/API.md` |
| Skills | ✅ | `bahram/skills/manager.py` | 3 bundled skills: `code-review`, `deploy`, `research` |
| Platforms | ⚠️ | `bahram/platforms/telegram.py`, `slack.py` | `slack` is imported by `bahram/cli.py`; `telegram.py` is not imported by anything in `bahram/` and is not installed by default (`pip install bahram-agent[telegram]`) |

---

## 6. Tests and quality gates

| Gate | Command | Status |
|---|---|---|
| Test suite | `pytest tests/ -q` | see `docs/ENGINEERING_REPORT.md` for the current count |
| Coverage | `pytest --cov=bahram --cov-fail-under=75` | ✅ ≥ 75 % overall; ≥ 85 % for core, security, memory, autonomy, tools |
| Lint | `ruff check bahram tests scripts` | ✅ 0 errors |
| Format | `ruff format --check bahram tests scripts` | ✅ clean |
| Types | `mypy bahram/core bahram/security` | ✅ clean |
| CI | `.github/workflows/ci.yml` | ✅ lint + pytest on 3.10/3.11/3.12 + wheel build/import/CLI smoke test |

Skips: the suite contains `pytest.mark.live` tests that talk to a real model
API. They skip without credentials and are excluded from coverage
expectations. No test is skipped to hide a failure.
