# Changelog

All notable changes to Bahram Agent will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-08-29

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
