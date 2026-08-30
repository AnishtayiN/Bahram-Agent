# Tool Registry Audit

## Registration Path

All tools are registered via `bahram/tools/__init__.py:init_tools()` which is called by `Agent._init_tools()` (`agent.py:177`). Each tool is instantiated and registered with `engine.register_tool(name, tool)` unless listed in `config.tools.disabled`.

---

## Registered Tools (11)

| # | Name | Class | Module | Schema | Security Pipeline | Source File |
|---|------|-------|--------|--------|-------------------|-------------|
| 1 | `bash` | `BashTool` | `bahram.tools.bash` | ✅ | TirithScanner + SupplyChainGuard | `tools/bash.py` |
| 2 | `read` | `ReadTool` | `bahram.tools.file` | ✅ | FileWriteSafety (read-only) | `tools/file.py:24` |
| 3 | `write` | `WriteTool` | `bahram.tools.file` | ✅ | FileWriteSafety | `tools/file.py` |
| 4 | `edit` | `EditTool` | `bahram.tools.file` | ✅ | FileWriteSafety | `tools/file.py` |
| 5 | `webfetch` | `WebFetchTool` | `bahram.tools.web` | ✅ | WebsitePolicy + SSRFProtector | `tools/web.py:33` |
| 6 | `websearch` | `WebSearchTool` | `bahram.tools.web` | ✅ | WebsitePolicy | `tools/web.py` |
| 7 | `execute_code` | `ExecuteCodeTool` | `bahram.tools.execute_code` | ✅ | Sandboxed subprocess | `tools/execute_code.py:13` |
| 8 | `git` | `GitTool` | `bahram.tools.extended` | ✅ | Subprocess shell | `tools/extended.py:12` |
| 9 | `process_list` | `ProcessListTool` | `bahram.tools.extended` | ✅ | Subprocess shell | `tools/extended.py` |
| 10 | `container` | `ContainerTool` | `bahram.tools.extended` | ✅ | Subprocess shell | `tools/extended.py` |
| 11 | `document_read` | `DocumentReadTool` | `bahram.tools.extended` | ✅ | File read | `tools/extended.py` |

### Registration Order

Registration follows the `init_tools()` function order in `tools/__init__.py`:
1. `bash` (line 16)
2. `read` (line 22)
3. `write` (line 23)
4. `edit` (line 24)
5. `webfetch` (line 30)
6. `websearch` (line 31)
7. `execute_code` (line 37)
8. `git` (line 43)
9. `process_list` (line 44)
10. `container` (line 45)
11. `document_read` (line 46)

---

## Unregistered Tools (exist but NOT wired into the runtime)

The following tool modules exist in `bahram/tools/` but are **not** imported or registered by `init_tools()`:

| Module | File | Notes |
|--------|------|-------|
| `terminal` | `tools/terminal.py` | Raw terminal, not registered |
| `terminal_enhanced` | `tools/terminal_enhanced.py` | Enhanced terminal, not registered |
| `code_review` | `tools/code_review.py` | Code review tool, not registered |
| `documentation` | `tools/documentation.py` | Doc generator, not registered |
| `api_generator` | `tools/api_generator.py` | API generator, not registered |
| `autocomplete` | `tools/autocomplete.py` | Autocomplete, not registered |
| `browser` | `tools/browser.py` | Browser tool, not registered |
| `bg_notify` | `tools/bg_notify.py` | Background notify, not registered |
| `clarify` | `tools/clarify.py` | Clarification, not registered |
| `code_search` | `tools/code_search.py` | Code search, not registered |
| `complexity` | `tools/complexity.py` | Complexity analysis, not registered |
| `database` | `tools/database.py` | Database tool, not registered |
| `dependency` | `tools/dependency.py` | Dependency analysis, not registered |
| `delegation` | `tools/delegation.py` | Delegation tool, not registered |
| `deployment` | `tools/deployment.py` | Deployment tool, not registered |
| `explainer` | `tools/explainer.py` | Code explainer, not registered |
| `formatter` | `tools/formatter.py` | Code formatter, not registered |
| `image_gen` | `tools/image_gen.py` | Image generation, not registered |
| `lsp` | `tools/lsp.py` | LSP integration, not registered |
| `migration` | `tools/migration.py` | Migration tool, not registered |
| `monitoring` | `tools/monitoring.py` | Monitoring tool, not registered |
| `optimizer` | `tools/optimizer.py` | Optimizer, not registered |
| `process` | `tools/process.py` | Process tool, not registered |
| `profiler` | `tools/profiler.py` | Profiler, not registered |
| `search` | `tools/search.py` | Search tool, not registered |
| `security_scan` | `tools/security_scan.py` | Security scan, not registered |
| `smart_completion` | `tools/smart_completion.py` | Smart completion, not registered |
| `smart_doc` | `tools/smart_doc.py` | Smart doc, not registered |
| `task` | `tools/task.py` | Task tool, not registered |
| `test_generator` | `tools/test_generator.py` | Test generator, not registered |
| `testing` | `tools/testing.py` | Testing tool, not registered |
| `todo` | `tools/todo.py` | Todo tool, not registered |
| `translator` | `tools/translator.py` | Translator, not registered |
| `websearch` (standalone) | `tools/websearch.py` | Standalone websearch, not registered |

**Total: 34 unregistered tool modules exist. None are on the critical path.**

---

## Execution Pipeline

All registered tools go through `ToolExecutor.execute()` (`engine.py:157`):

```
Tool Call Request
    ↓
ToolExecutor.execute(tool_call, timeout)
    ↓
Tool name lookup (engine.tools dict)
    ↓
ApprovalSystem.check_command(command_string)
    ↓ (if dangerous + critical/high risk)
BLOCKED — returns error
    ↓ (if safe or low/medium risk)
asyncio.wait_for(tool.execute(**args), timeout=120s)
    ↓
ToolResult(success/content/error)
    ↓
Event logged to executor._log
```

### Security Filtering

The `ToolExecutor._get_command_string()` method (`engine.py:204`) extracts the command for security review:
- `bash` → `arguments["command"]`
- `execute_code` → `arguments["code"]`
- All others → `f"{tool_name}({json.dumps(arguments)[:200]})"`

Critical/high risk commands are blocked by `ApprovalSystem` before execution. Medium/low risk commands proceed with logging.

---

## MCP Tool Integration

MCP tools are registered in `Agent._init_mcp_tools()` (`agent.py:140`). Each discovered MCP tool is wrapped in `_MCPToolAdapter` (`agent.py:562`) and registered with prefix `mcp_`:
- `_MCPToolAdapter.schema()` returns the MCP tool's name, description, and inputSchema
- `_MCPToolAdapter.execute(**kwargs)` delegates to `client.call_tool(name, kwargs)`

MCP tools follow the same execution pipeline as native tools (ToolExecutor → ApprovalSystem → execute).

---

## Summary

| Metric | Value |
|--------|-------|
| Registered tools | 11 |
| Unregistered tool modules | 34 |
| Security pipeline coverage | 100% (all go through ApprovalSystem) |
| Tool timeout | 120s (configurable via `config.tools.bash_timeout`) |
| MCP tools | Dynamic (discovered at runtime) |
| Tool schemas | All registered tools implement `schema()` |
| Execution method | All tools implement `execute(**kwargs)` |
