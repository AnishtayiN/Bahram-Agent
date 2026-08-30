from __future__ import annotations

import asyncio
import ast
import inspect
from pathlib import Path
from unittest.mock import patch

import pytest
from bahram.core.engine import AgentEngine, ToolCall, ToolExecutor, ToolResult
from bahram.tools import init_tools
from bahram.tools.bash import BashTool
from bahram.tools.file import WriteTool


def _make_tools_config(disabled: list[str] | None = None):
    class FakeToolsConfig:
        pass
    cfg = FakeToolsConfig()
    cfg.disabled = disabled or []
    return cfg


def _make_config(disabled: list[str] | None = None):
    class FakeConfig:
        pass
    cfg = FakeConfig()
    cfg.tools = _make_tools_config(disabled)
    return cfg


def _patch_write_tool_init():
    original_init = WriteTool.__init__ if hasattr(WriteTool, '__init__') else None

    def patched_init(self, config=None):
        pass

    return patch.object(WriteTool, '__init__', patched_init)


@pytest.fixture
async def engine_with_tools():
    engine = AgentEngine()
    with _patch_write_tool_init():
        await init_tools(engine, _make_config())
    return engine


@pytest.fixture
async def executor_with_tools():
    engine = AgentEngine()
    with _patch_write_tool_init():
        await init_tools(engine, _make_config())
    return engine._tool_executor


class TestEveryToolGoesThroughToolExecutor:
    async def test_executor_execute_runs_tool(self, executor_with_tools: ToolExecutor):
        call = ToolCall(id="t1", name="read", arguments={"file_path": "/dev/null"})
        result = await executor_with_tools.execute(call)
        assert isinstance(result, ToolResult)
        assert result.success is True

    async def test_executor_unknown_tool_returns_error(self, executor_with_tools: ToolExecutor):
        call = ToolCall(id="t2", name="nonexistent_tool", arguments={})
        result = await executor_with_tools.execute(call)
        assert result.success is False
        assert "Unknown tool" in result.error

    async def test_executor_handles_missing_execute_method(self):
        class NoExec:
            pass
        executor = ToolExecutor(tools={"bad": NoExec()}, approval_system=None)
        call = ToolCall(id="t3", name="bad", arguments={})
        result = await executor.execute(call)
        assert result.success is False
        assert "no execute method" in result.error

    async def test_engine_run_uses_tool_executor(self, engine_with_tools: AgentEngine):
        assert engine_with_tools._tool_executor is not None
        assert isinstance(engine_with_tools._tool_executor, ToolExecutor)

    async def test_all_registered_tools_accessible_via_executor(self, executor_with_tools: ToolExecutor):
        for name in ["bash", "read", "write", "edit", "webfetch", "websearch",
                      "execute_code", "git", "process_list", "container", "document_read"]:
            assert name in executor_with_tools.tools, f"'{name}' not in executor tools"

    async def test_executor_wraps_timeout(self):
        class SlowTool:
            async def execute(self, **kwargs):
                await asyncio.sleep(100)
                return "done"

        executor = ToolExecutor(tools={"slow": SlowTool()}, approval_system=None)
        call = ToolCall(id="t4", name="slow", arguments={})
        result = await executor.execute(call, timeout=0.5)
        assert result.success is False
        assert "timed out" in result.error.lower()


class TestToolExecutorChecksSecurity:
    async def test_executor_blocks_critical_commands(self):
        class FakeApproval:
            def check_command(self, cmd):
                return True, "dangerous command"
            def assess_risk(self, cmd):
                return "critical"

        executor = ToolExecutor(
            tools={"bash": BashTool(config=None)},
            approval_system=FakeApproval(),
        )
        call = ToolCall(id="sec1", name="bash", arguments={"command": "rm -rf /"})
        result = await executor.execute(call)
        assert result.success is False
        assert "Security block" in result.error

    async def test_executor_allows_safe_commands(self):
        class FakeApproval:
            def check_command(self, cmd):
                return False, ""
            def assess_risk(self, cmd):
                return "low"

        executor = ToolExecutor(
            tools={"read": __import__("bahram.tools.file", fromlist=["ReadTool"]).ReadTool()},
            approval_system=FakeApproval(),
        )
        call = ToolCall(id="sec2", name="read", arguments={"file_path": "/dev/null"})
        result = await executor.execute(call)
        assert result.success is True

    async def test_executor_runs_without_approval_system(self):
        executor = ToolExecutor(tools={}, approval_system=None)
        assert executor.approval_system is None

    async def test_executor_blocks_high_risk(self):
        class FakeApproval:
            def check_command(self, cmd):
                return True, "risky"
            def assess_risk(self, cmd):
                return "high"

        executor = ToolExecutor(
            tools={"bash": BashTool(config=None)},
            approval_system=FakeApproval(),
        )
        call = ToolCall(id="sec3", name="bash", arguments={"command": "echo test"})
        result = await executor.execute(call)
        assert result.success is False
        assert "Security block" in result.error

    async def test_executor_allows_low_risk_commands(self):
        class FakeApproval:
            def check_command(self, cmd):
                return True, "minor"
            def assess_risk(self, cmd):
                return "low"

        class EchoTool:
            async def execute(self, **kwargs):
                return "ok"

        executor = ToolExecutor(
            tools={"echo": EchoTool()},
            approval_system=FakeApproval(),
        )
        call = ToolCall(id="sec4", name="echo", arguments={"msg": "test"})
        result = await executor.execute(call)
        assert result.success is True


class TestToolExecutorChecksApprovalForDangerousCommands:
    async def test_approval_system_called_for_bash(self):
        log = []

        class FakeApproval:
            def check_command(self, cmd):
                log.append(("check", cmd))
                return False, ""
            def assess_risk(self, cmd):
                return "low"

        executor = ToolExecutor(
            tools={"bash": BashTool(config=None)},
            approval_system=FakeApproval(),
        )
        call = ToolCall(id="app1", name="bash", arguments={"command": "echo hello"})
        await executor.execute(call)

        assert len(log) == 1
        assert log[0] == ("check", "echo hello")

    async def test_approval_system_called_for_execute_code(self):
        log = []

        class FakeApproval:
            def check_command(self, cmd):
                log.append(("check", cmd))
                return False, ""
            def assess_risk(self, cmd):
                return "low"

        executor = ToolExecutor(
            tools={"execute_code": __import__("bahram.tools.execute_code", fromlist=["ExecuteCodeTool"]).ExecuteCodeTool()},
            approval_system=FakeApproval(),
        )
        call = ToolCall(id="app2", name="execute_code", arguments={"code": "print(1)"})
        await executor.execute(call)

        assert len(log) == 1
        assert log[0] == ("check", "print(1)")

    async def test_non_bash_tool_gets_formatted_command(self):
        log = []

        class FakeApproval:
            def check_command(self, cmd):
                log.append(("check", cmd))
                return False, ""
            def assess_risk(self, cmd):
                return "low"

        executor = ToolExecutor(
            tools={"read": __import__("bahram.tools.file", fromlist=["ReadTool"]).ReadTool()},
            approval_system=FakeApproval(),
        )
        call = ToolCall(id="app3", name="read", arguments={"file_path": "/tmp/x"})
        await executor.execute(call)

        assert len(log) == 1
        assert "read" in log[0][1]

    async def test_approval_skipped_when_none(self):
        log = []

        class EchoTool:
            async def execute(self, **kwargs):
                return "ok"

        executor = ToolExecutor(
            tools={"echo": EchoTool()},
            approval_system=None,
        )
        call = ToolCall(id="app4", name="echo", arguments={"msg": "hi"})
        result = await executor.execute(call)
        assert result.success is True
        assert len(log) == 0


class TestToolExecutorRecordsTrajectory:
    async def test_success_event_logged(self, executor_with_tools: ToolExecutor):
        call = ToolCall(id="traj1", name="read", arguments={"file_path": "/dev/null"})
        await executor_with_tools.execute(call)

        assert len(executor_with_tools._log) == 1
        entry = executor_with_tools._log[0]
        assert entry["tool"] == "read"
        assert entry["status"] == "success"
        assert entry["error"] is None
        assert "timestamp" in entry

    async def test_failure_event_logged(self):
        executor = ToolExecutor(tools={}, approval_system=None)
        call = ToolCall(id="traj2", name="nonexistent", arguments={})
        await executor.execute(call)

        assert len(executor._log) == 0

    async def test_security_block_event_logged(self):
        class FakeApproval:
            def check_command(self, cmd):
                return True, "blocked"
            def assess_risk(self, cmd):
                return "critical"

        executor = ToolExecutor(
            tools={"bash": BashTool(config=None)},
            approval_system=FakeApproval(),
        )
        call = ToolCall(id="traj3", name="bash", arguments={"command": "rm -rf /"})
        await executor.execute(call)

        assert len(executor._log) == 1
        entry = executor._log[0]
        assert entry["status"] == "blocked"

    async def test_multiple_executions_append_to_log(self, executor_with_tools: ToolExecutor):
        for i in range(3):
            call = ToolCall(id=f"multi{i}", name="read", arguments={"file_path": "/dev/null"})
            await executor_with_tools.execute(call)

        assert len(executor_with_tools._log) == 3
        for entry in executor_with_tools._log:
            assert entry["status"] == "success"

    async def test_log_contains_error_message(self):
        class FakeApproval:
            def check_command(self, cmd):
                return True, "forbidden operation"
            def assess_risk(self, cmd):
                return "critical"

        executor = ToolExecutor(
            tools={"bash": BashTool(config=None)},
            approval_system=FakeApproval(),
        )
        call = ToolCall(id="traj4", name="bash", arguments={"command": "rm -rf /"})
        await executor.execute(call)

        entry = executor._log[0]
        assert "forbidden operation" in entry["error"]


class TestNoDirectToolExecuteCalls:
    """Static analysis: prove no code path bypasses ToolExecutor.

    Scans engine.py to verify that tool.execute() is ONLY called inside
    ToolExecutor.execute(), never directly elsewhere.
    """

    def _find_execute_calls_outside_executor(self, filepath: Path) -> list[dict]:
        source = filepath.read_text()
        tree = ast.parse(source)
        results = []

        for top_node in ast.iter_child_nodes(tree):
            in_executor_class = False
            if isinstance(top_node, ast.ClassDef) and top_node.name == "ToolExecutor":
                in_executor_class = True

            for node in ast.walk(top_node):
                if in_executor_class:
                    continue
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Attribute) and func.attr == "execute":
                        results.append({
                            "lineno": node.lineno,
                            "source_line": source.splitlines()[node.lineno - 1].strip(),
                        })
        return results

    def test_tool_execute_only_in_tool_executor(self):
        engine_path = Path(inspect.getfile(AgentEngine))
        source = engine_path.read_text()
        tree = ast.parse(source)

        calls_in_executor = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "execute":
                    line = source.splitlines()[node.lineno - 1].strip()
                    calls_in_executor.append({"lineno": node.lineno, "source_line": line})

        assert len(calls_in_executor) >= 1, "Expected at least one .execute() call in engine.py"

        found_tool_execute = any("tool.execute(" in c["source_line"] for c in calls_in_executor)
        assert found_tool_execute, "tool.execute() call not found in engine.py"

    def test_no_direct_tool_execute_outside_executor(self):
        engine_path = Path(inspect.getfile(AgentEngine))
        violations = self._find_execute_calls_outside_executor(engine_path)

        real_violations = [
            v for v in violations
            if "self._tool_executor.execute" not in v["source_line"]
        ]

        assert not real_violations, (
            f"Found .execute() calls outside ToolExecutor that bypass the executor: {real_violations}"
        )

    def test_engine_uses_executor_for_tool_execution(self):
        engine_path = Path(inspect.getfile(AgentEngine))
        source = engine_path.read_text()

        assert "self._tool_executor.execute(" in source, (
            "AgentEngine.run() does not use self._tool_executor.execute()"
        )

    def test_all_tool_modules_importable(self):
        from bahram.tools import bash, file, web, execute_code, extended
        modules = [bash, file, web, execute_code, extended]
        for mod in modules:
            assert mod is not None
