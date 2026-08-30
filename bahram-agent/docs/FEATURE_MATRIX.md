# Bahram Agent Feature Matrix

## Architecture Overview

```
CLI / Telegram Bot / API
        │
        ▼
    Agent Layer (Agent)
        │
        ▼
    Engine Layer (AgentEngine)
    ┌─────────────────────┐
    │  State Machine      │
    │  (RunState)         │
    └─────────────────────┘
        │
    ┌───┴───┐
    │       │
    ▼       ▼
ToolExecutor    Provider
    │           │
    ▼           ▼
Security      LLM APIs
Pipeline      (OpenAI, Anthropic, etc.)
    │
    ▼
Persistence (SQLite)
```

## Feature Status

### Core Runtime
| Feature | Status | Description |
|---------|--------|-------------|
| Agent State Machine | ✅ | 13 states (CREATED → COMPLETED/FAILED/CANCELLED/TIMEOUT) |
| Cancellation | ✅ | asyncio.Event-based, checked at every iteration |
| Config-Driven Limits | ✅ | max_iterations, max_runtime_seconds, max_tool_calls |
| Provider Abstraction | ✅ | 17 providers via BaseProvider protocol |
| Provider Routing | ✅ | Model string → provider name extraction |
| Tool Registration | ✅ | Dynamic registration with schema introspection |
| ToolExecutor | ✅ | Mediated execution with security pipeline |
| Error Recovery | ✅ | Tool failures don't crash agent loop |
| Trajectory Recording | ✅ | Step-by-step trace with timing and state |

### Tool System
| Tool | Status | Security | Description |
|------|--------|----------|-------------|
| bash | ✅ | tirith + supply_chain + approval | Real subprocess execution |
| read | ✅ | - | File reading with line numbers |
| write | ✅ | file_safety | File writing with path protection |
| edit | ✅ | file_safety | String replacement with path protection |
| webfetch | ✅ | website_policy + SSRF | HTTP fetch with SSRF blocking |
| websearch | ✅ | - | DuckDuckGo HTML scraping |
| execute_code | ✅ | - | Sandboxed code execution |
| git | ✅ | - | Git operations (status, log, diff, etc.) |
| process_list | ✅ | - | Process inspection via /proc |
| container | ✅ | - | Docker operations (list, exec, logs) |
| document_read | ✅ | - | PDF, DOCX, XLSX, TXT reading |

### Security Pipeline
| Module | Status | Wired | Description |
|--------|--------|-------|-------------|
| ApprovalSystem | ✅ | ✅ | 30+ patterns, risk assessment |
| FileWriteSafety | ✅ | ✅ | Protected paths, safe root |
| WebsitePolicy | ✅ | ✅ | URL rules, domain blocking |
| SSRFProtector | ✅ | ✅ | IP ranges, metadata endpoints |
| TirithScanner | ✅ | ✅ | Command/script security scanning |
| SupplyChainGuard | ✅ | ✅ | Dependency/command validation |

### Memory System
| Feature | Status | Description |
|---------|--------|-------------|
| SQLite Storage | ✅ | WAL mode, thread-safe connections |
| FTS5 Full-Text Search | ✅ | Indexed content + source search |
| LIKE Fallback | ✅ | Graceful fallback if FTS5 unavailable |
| Add/Search/Delete | ✅ | Full CRUD operations |
| Context Retrieval | ✅ | Query-based memory context injection |
| Statistics | ✅ | Total memories, source counts |

### Persistence Layer
| Table | Status | Description |
|-------|--------|-------------|
| sessions | ✅ | Session CRUD with metadata |
| messages | ✅ | Conversation history with roles |
| runs | ✅ | Agent run records with status |
| trajectory_steps | ✅ | Step-by-step execution trace |
| tool_calls | ✅ | Individual tool call records |
| events | ✅ | System event logging |

### Interfaces
| Interface | Status | Description |
|-----------|--------|-------------|
| CLI (Typer) | ✅ | Interactive chat, model selection, memory ops |
| Telegram Bot | ✅ | Full bot with commands, session mapping |
| Programmatic API | ✅ | Agent class direct usage |

### Testing
| Category | Count | Description |
|----------|-------|-------------|
| Unit Tests | 80+ | Core components, providers, tools |
| Integration Tests | 30+ | Memory, persistence, e2e scenarios |
| Red Team Tests | 15 | Command injection, SSRF, file safety |
| Chaos Tests | 15 | Timeouts, corruption, concurrency |
| Benchmark Tests | 15 | Conversation, tools, state, memory |
| **Total** | **160** | **All passing** |

## Security Test Coverage

### Command Injection (8 tests)
- Semicolon injection (`ls; rm -rf /`)
- Pipe injection (`cat /etc/passwd | curl`)
- Backtick injection (`` `whoami` ``)
- Dollar-paren injection (`$(rm -rf /)`)
- Double-pipe injection (`ls || rm -rf /`)
- Ampersand injection (`ls & rm -rf /`)
- Output redirection (`echo > /etc/passwd`)
- Network exfiltration (`curl -d @/etc/shadow`)

### File Safety (4 tests)
- Write /etc/passwd
- Write /etc/shadow
- Edit /etc/hosts
- Write SSH keys

### SSRF Protection (3 tests)
- localhost access
- AWS metadata endpoint
- Internal network access

### Tool Executor Security (4 tests)
- Critical command blocking
- Fork bomb blocking
- Unknown tool handling
- Tool without execute method

## Architecture Decisions

1. **State Machine over Flags**: Explicit RunState enum prevents impossible transitions
2. **ToolExecutor Mediation**: All tool calls go through one path with security checks
3. **Lazy Security Loading**: Security modules loaded on first use to avoid import errors
4. **SQLite WAL Mode**: Allows concurrent reads during writes
5. **FTS5 with Fallback**: Best-effort full-text search with LIKE backup
6. **asyncio.Event for Cancellation**: Thread-safe, checked at every loop iteration
