# Feature Trace

Every feature traced from entry point to execution.

## Agent Runtime

| Feature | Entry Point | Implementation | Runtime Path | Tests | Status |
|---------|------------|---------------|-------------|-------|--------|
| Agent.chat() | CLI / Telegram | `bahram/core/agent.py` | Agent → Engine → Provider → Response | test_agent.py, test_e2e.py | REAL |
| Agent.run() | CLI / Telegram | `bahram/core/agent.py` | Agent → context build → memory → engine → response | test_agent.py | REAL |
| Agent.chat_streaming() | CLI | `bahram/core/agent.py` | Agent → Engine → Provider.stream | test_agent.py | REAL |
| Session management | CLI / Telegram | `bahram/core/agent.py` | create_session → SessionStore → context | test_agent.py, test_e2e.py | REAL |
| Context management | Runtime | `bahram/core/context.py` | ContextWindow → trim → preserve system | test_core.py, test_e2e.py | REAL |
| System prompt | Runtime | `bahram/core/agent.py` | _build_system_prompt → tools list | test_agent.py | REAL |

## Providers

| Feature | Entry Point | Implementation | Runtime Path | Tests | Status |
|---------|------------|---------------|-------------|-------|--------|
| OpenAI | Engine | `bahram/providers/openai.py` | httpx → API → parse → AgentResponse | test_providers.py | REAL |
| Anthropic | Engine | `bahram/providers/anthropic.py` | httpx → API → parse → AgentResponse | test_providers.py | REAL |
| Groq | Engine | `bahram/providers/groq.py` | httpx → API → parse → AgentResponse | test_providers.py | REAL |
| DeepSeek | Engine | `bahram/providers/deepseek.py` | httpx → API → parse → AgentResponse | test_providers.py | REAL |
| Mistral | Engine | `bahram/providers/mistral.py` | httpx → API → parse → AgentResponse | test_providers.py | REAL |
| OpenRouter | Engine | `bahram/providers/openrouter.py` | httpx → API → parse → AgentResponse | test_providers.py | REAL |
| Ollama | Engine | `bahram/providers/ollama.py` | httpx → API → parse → AgentResponse | test_providers.py | REAL |
| Google | Engine | `bahram/providers/google.py` | httpx → API → parse → AgentResponse | test_providers.py | REAL |
| 9 more providers | Engine | `bahram/providers/*.py` | OpenAI-compatible pattern | test_providers.py | REAL |

## Tools

| Feature | Entry Point | Implementation | Runtime Path | Tests | Status |
|---------|------------|---------------|-------------|-------|--------|
| bash | Agent.chat → Engine | `bahram/tools/bash.py` | asyncio.subprocess → timeout → output | test_core.py | REAL |
| read | Agent.chat → Engine | `bahram/tools/file.py` | Path.open → lines → formatted | test_core.py | REAL |
| write | Agent.chat → Engine | `bahram/tools/file.py` | Path.open → write | test_core.py | REAL |
| edit | Agent.chat → Engine | `bahram/tools/file.py` | str.replace → write | test_core.py | REAL |
| webfetch | Agent.chat → Engine | `bahram/tools/web.py` | httpx → parse → text | test_tools.py | REAL |
| websearch | Agent.chat → Engine | `bahram/tools/web.py` | httpx → DuckDuckGo → parse | test_tools.py | REAL |
| execute_code | Agent.chat → Engine | `bahram/tools/execute_code.py` | subprocess → timeout → output | test_tools.py | REAL |

## Security

| Feature | Entry Point | Implementation | Runtime Path | Tests | Status |
|---------|------------|---------------|-------------|-------|--------|
| Command approval | Engine.execute_tool | `bahram/security/approval.py` | ApprovalSystem.check_command → risk | test_security.py, test_e2e.py | REAL |
| Dangerous block | Engine.execute_tool | `bahram/security/approval.py` | HARDLINE_BLOCKLIST → block | test_security.py, test_e2e.py | REAL |
| Risk assessment | Engine.execute_tool | `bahram/security/approval.py` | assess_risk → critical/high/medium/low | test_security.py | REAL |
| File safety | Tool level | `bahram/security/file_safety.py` | path check → protected paths | test_security.py | REAL |
| Code scanning | Tool level | `bahram/security/tirith.py` | pattern scan → safe/dangerous | test_security.py | REAL |

## Memory

| Feature | Entry Point | Implementation | Runtime Path | Tests | Status |
|---------|------------|---------------|-------------|-------|--------|
| Store memory | Agent.chat | `bahram/memory/semantic.py` | add → JSON persist | test_memory.py, test_e2e.py | REAL |
| Retrieve memory | Agent.chat | `bahram/memory/semantic.py` | search → ranking → context | test_memory.py, test_e2e.py | REAL |
| Memory in context | Agent.chat | `bahram/core/agent.py` | _retrieve_memories → inject | test_e2e.py | REAL |

## Persistence

| Feature | Entry Point | Implementation | Runtime Path | Tests | Status |
|---------|------------|---------------|-------------|-------|--------|
| Session store | Agent | `bahram/core/persistence.py` | SQLite → WAL → transactions | test_persistence.py, test_e2e.py | REAL |
| Message persistence | Agent.chat | `bahram/core/persistence.py` | add_message → SQLite | test_persistence.py, test_e2e.py | REAL |
| Session list | Agent | `bahram/core/persistence.py` | list_sessions → SQLite | test_persistence.py | REAL |

## Trajectory

| Feature | Entry Point | Implementation | Runtime Path | Tests | Status |
|---------|------------|---------------|-------------|-------|--------|
| Step recording | Engine.run | `bahram/core/engine.py` | TrajectoryStep → Trajectory | test_e2e.py | REAL |
| Tool call tracking | Engine.run | `bahram/core/engine.py` | tool_calls → tool_results | test_e2e.py | REAL |
| Duration tracking | Engine.run | `bahram/core/engine.py` | step_duration → total_duration | test_e2e.py | REAL |

## Telegram

| Feature | Entry Point | Implementation | Runtime Path | Tests | Status |
|---------|------------|---------------|-------------|-------|--------|
| Bot commands | bot.py | `bot.py` | Telegram → BahramTelegramBot → Agent | Manual | REAL |
| Message handling | bot.py | `bot.py` | handle_message → _process_message → Agent.chat | Manual | REAL |
| Session mapping | bot.py | `bot.py` | chat_id → session_id | Manual | REAL |

## CLI

| Feature | Entry Point | Implementation | Runtime Path | Tests | Status |
|---------|------------|---------------|-------------|-------|--------|
| chat command | cli.py | `bahram/cli.py` | typer → Agent.chat | Manual | REAL |
| Interactive mode | cli.py | `bahram/cli.py` | Prompt.ask → Agent.chat_streaming | Manual | REAL |
