# Hermes Parity Matrix

| # | Capability | Hermes | Bahram | Gap | Priority |
|---|-----------|--------|--------|-----|----------|
| 1 | Agent Runtime | Full loop with streaming | Full loop, streaming partial | Streaming tool calls | Medium |
| 2 | Agent Loop | Iterative LLM + tools | Iterative LLM + tools + budget | Same level | Low |
| 3 | Prompt Assembly | System + context + memory | System + context + memory + skills | Same level | Low |
| 4 | Context Management | Smart context with categories | SmartContext + ContextArchitecture | Not wired together | High |
| 5 | Memory | Multi-scope with FTS5 | Scope + importance + confidence + FTS5 | No embedding search | Medium |
| 6 | User Profile | Persistent profile | Profile via memory scope | No structured profile model | Medium |
| 7 | Skills | Full lifecycle | Candidate → Trusted lifecycle | No human approval | Medium |
| 8 | Learning | LLM-assisted | Rule-based + template | No LLM in lesson extraction | High |
| 9 | Tool System | Registry + executor | Registry + executor + approval | Same level | Low |
| 10 | Tool Gateway | Contextual tool selection | ToolGateway with search + risk | Not wired into engine | High |
| 11 | MCP | Full MCP support | JSON-RPC client/server | No streaming | Medium |
| 12 | Provider Abstraction | Canonical types | Canonical types | Same level | Low |
| 13 | Model Routing | Task-based routing | Basic routing | No complexity-based routing | Medium |
| 14 | Provider Failover | Retry + fallback | FallbackProvider + circuit breaker | Same level | Low |
| 15 | Security | Capability-based | SecurityKernel + ApprovalSystem | Not fully wired | High |
| 16 | Approval | Interactive | Pattern-based blocking | No interactive UI | Medium |
| 17 | Terminal | Sandboxed shell | BashTool with approval | No true sandbox | Medium |
| 18 | Browser | Full browser | Not implemented | Gap | Low |
| 19 | Delegation | Multi-agent | SubagentEngine | Same level | Low |
| 20 | Subagents | Child runs with isolation | SubagentEngine with concurrency | No result verification | Medium |
| 21 | Background Jobs | Durable jobs | JobEngine with SQLite | Not wired from Agent | High |
| 22 | Cron/Scheduling | Recurring tasks | Not implemented | Gap | Low |
| 23 | Gateway | Full gateway | GatewayService exists | Not functional | High |
| 24 | Telegram | Full bot with approval | TelegramPlatform | No callback approval | High |
| 25 | Session Persistence | Full session store | SessionStore with SQLite | Same level | Low |
| 26 | Recovery | Crash recovery | RecoveryManager checkpoints | No auto-restart | Medium |
| 27 | Observability | Structured events | Observability class (25+ events) | Not fully wired | Medium |
| 28 | Trajectory | Full trajectory | Trajectory persisted to JSON | Same level | Low |
| 29 | Cost Control | Budget + cost tracking | BudgetManager + CostModel | Model param now passed | Low |
| 30 | Testing | Comprehensive | 836 tests across 50+ files | Same level | Low |
