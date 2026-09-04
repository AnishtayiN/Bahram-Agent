"""Behavioural tests for the tools/capability modules (batch D).

Covers: task, terminal, terminal_enhanced, test_generator, testing, todo,
translator, webfetch, websearch.

The two HTTP-backed helpers (tools/webfetch.py, tools/websearch.py) talk to a
real loopback HTTP server or, where the host is hardcoded to an external
vendor, to httpx's in-process ``MockTransport``.  Both are external network
boundaries; no project code is stubbed.

``TerminalTool``'s PTY path calls ``os.fork()``, which is unsafe inside the
pytest process itself, so that one test runs the code in a child interpreter
and asserts on the JSON it prints.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from bahram.tools.task import Task, TaskTool
from bahram.tools.terminal import (
    PTYManager,
    ShellInitHandler,
    SudoManager,
    TerminalConfig,
    TerminalTool,
)
from bahram.tools.terminal_enhanced import (
    PTYManager as EnhancedPTYManager,
)
from bahram.tools.terminal_enhanced import (
    PTYSession,
)
from bahram.tools.terminal_enhanced import (
    ShellInitHandler as EnhancedShellInitHandler,
)
from bahram.tools.terminal_enhanced import (
    SudoManager as EnhancedSudoManager,
)
from bahram.tools.test_generator import GeneratedTest
from bahram.tools.test_generator import TestGenerator as CodeTestGenerator
from bahram.tools.testing import TestCase as RunnerTestCase
from bahram.tools.testing import TestRunner as ToolTestRunner
from bahram.tools.todo import TodoItem, TodoTool
from bahram.tools.translator import CodeTranslator, TranslationRule
from bahram.tools.webfetch import WebFetchTool
from bahram.tools.websearch import WebSearchTool


# ---------------------------------------------------------------------------
# task
# ---------------------------------------------------------------------------
class TestTaskTool:
    async def test_launch_sync_function(self):
        tool = TaskTool()
        task = await tool.launch("t1", "double", lambda a: a * 2, 21)
        assert task.status == "completed"
        assert task.result == 42
        assert task.end_time >= task.start_time

    async def test_launch_async_function(self):
        async def work(a: int) -> int:
            await asyncio.sleep(0)
            return a + 1

        task = await TaskTool().launch("t1", "inc", work, 1)
        assert task.result == 2

    async def test_failing_task_records_error(self):
        def boom():
            raise ValueError("bad input")

        task = await TaskTool().launch("t1", "boom", boom)
        assert task.status == "failed"
        assert task.error == "bad input"
        assert task.end_time > 0  # the timer is closed out even on failure

    async def test_callback_runs_after_completion(self):
        seen: list[Task] = []

        async def on_done(task: Task) -> None:
            seen.append(task)

        tool = TaskTool()
        tool.set_callback("t1", on_done)
        await tool.launch("t1", "job", lambda: "ok")
        assert seen and seen[0].result == "ok"

    async def test_failing_callback_is_contained(self):
        async def boom(task: Task) -> None:
            raise RuntimeError("callback failed")

        tool = TaskTool()
        tool.set_callback("t1", boom)
        task = await tool.launch("t1", "job", lambda: "ok")
        assert task.status == "completed"

    def test_accessors(self):
        tool = TaskTool()
        assert tool.get_status("nope") == "not_found"
        assert tool.get_result("nope") is None
        assert tool.get_task("nope") is None

    def test_get_result_only_for_completed(self):
        tool = TaskTool()
        tool._tasks["t1"] = Task(task_id="t1", name="n", status="failed")
        assert tool.get_result("t1") is None

    def test_cancel_running_task(self):
        tool = TaskTool()
        tool._tasks["t1"] = Task(task_id="t1", name="n", status="running")
        assert tool.cancel("t1") is True
        assert tool.get_status("t1") == "cancelled"

    def test_cancel_unknown_or_finished_task(self):
        tool = TaskTool()
        assert tool.cancel("nope") is False
        tool._tasks["t1"] = Task(task_id="t1", name="n", status="completed")
        assert tool.cancel("t1") is False

    def test_list_tasks_reports_duration(self):
        tool = TaskTool()
        task = Task(task_id="t1", name="n", status="completed", start_time=1.0, end_time=3.0)
        tool._tasks["t1"] = task
        assert tool.list_tasks() == [
            {"id": "t1", "name": "n", "status": "completed", "duration": 2.0}
        ]

    def test_task_defaults(self):
        task = Task(task_id="t1", name="n")
        assert (task.status, task.result, task.error) == ("pending", None, "")


# ---------------------------------------------------------------------------
# terminal
# ---------------------------------------------------------------------------
class TestPTYManager:
    def test_create_write_read_close(self):
        manager = PTYManager()
        master_fd, slave_fd = manager.create_session(TerminalConfig())

        manager.write_session(master_fd, "echo hello\n")
        output = ""
        for _ in range(50):
            chunk = manager.read_session(master_fd, 0.1)
            output += chunk
            if "hello" in output:
                break

        assert "hello" in output
        manager.close_session(master_fd)
        manager.close_session(master_fd)  # second close must not raise

    def test_read_after_close_returns_empty(self):
        manager = PTYManager()
        master_fd, _slave_fd = manager.create_session(TerminalConfig())
        manager.close_session(master_fd)
        assert manager.read_session(master_fd) == ""


class TestSudoManager:
    def test_password_cache_expires(self):
        manager = SudoManager()
        assert manager.get_password("host") is None

        manager.cache_password("host", "secret")
        assert manager.get_password("host") == "secret"

        manager._cache_timestamps["host"] -= 10_000
        assert manager.get_password("host") is None
        assert "host" not in manager._password_cache

    def test_clear_password(self):
        manager = SudoManager()
        manager.cache_password("host", "secret")
        manager.clear_password("host")
        assert manager.get_password("host") is None


class TestShellInitHandler:
    def test_init_script_selected_by_shell(self):
        handler = ShellInitHandler()
        assert handler.get_init_script("/bin/bash") == handler._get_bash_init()
        assert handler.get_init_script("/usr/bin/zsh") == handler._get_zsh_init()
        assert handler.get_init_script("/usr/bin/fish") == handler._get_fish_init()

    def test_wrap_command_prepends_init(self):
        handler = ShellInitHandler()
        assert handler.wrap_command("ls", "/bin/bash").endswith("\nls")

    def test_guard_patterns_cover_common_interactive_checks(self):
        handler = ShellInitHandler()
        assert any("$-" in p for p in handler._guard_patterns)
        assert any("tty" in p for p in handler._guard_patterns)

    def test_terminal_config_defaults(self):
        cfg = TerminalConfig()
        assert cfg.shell == "/bin/bash"
        assert cfg.use_pty is True
        assert cfg.timeout == 60.0


class TestTerminalTool:
    async def test_subprocess_mode_returns_streams_and_exit_code(self):
        tool = TerminalTool()
        result = await tool.execute("echo out; echo err 1>&2", config=TerminalConfig(use_pty=False))
        assert result["exit_code"] == 0
        assert "out" in result["stdout"]
        assert "err" in result["stderr"]

    async def test_subprocess_mode_reports_nonzero_exit(self):
        tool = TerminalTool()
        result = await tool.execute("exit 3", config=TerminalConfig(use_pty=False))
        assert result["exit_code"] == 3

    async def test_subprocess_mode_times_out(self):
        tool = TerminalTool()
        result = await tool.execute("sleep 5", config=TerminalConfig(use_pty=False, timeout=0.3))
        assert result["exit_code"] == -1
        assert result["stderr"] == "Command timed out"

    async def test_pty_mode_runs_in_a_child_interpreter(self):
        """_execute_pty forks, so run it outside the pytest process."""
        program = (
            "import asyncio, json\n"
            "from bahram.tools.terminal import TerminalConfig, TerminalTool\n"
            "tool = TerminalTool()\n"
            "result = asyncio.run(\n"
            "    tool.execute(\n"
            '        "echo pty-works",\n'
            "        config=TerminalConfig(use_pty=True, shell='/bin/bash'),\n"
            "    )\n"
            ")\n"
            "print(json.dumps(result))\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(Path(__file__).resolve().parents[1]),
            env={"PYTHONPATH": str(Path(__file__).resolve().parents[1]), "PATH": "/usr/bin:/bin"},
        )
        assert completed.returncode == 0, completed.stderr
        assert "pty-works" in json.loads(completed.stdout)["stdout"]

    async def test_sudo_mode_does_not_wrap_command(self):
        tool = TerminalTool()
        captured: dict[str, str] = {}

        async def fake_pty(command, config):
            captured["command"] = command
            return {"stdout": "", "stderr": "", "exit_code": 0}

        tool._execute_pty = fake_pty  # type: ignore[method-assign]
        await tool.execute("whoami", config=TerminalConfig(sudo=True))
        assert captured["command"] == "whoami"


# ---------------------------------------------------------------------------
# terminal_enhanced
# ---------------------------------------------------------------------------
class TestEnhancedPTYManager:
    def test_create_session_forks_a_real_process(self, tmp_path: Path):
        manager = EnhancedPTYManager()
        session = manager.create_session(command="/bin/cat", cwd=str(tmp_path))

        assert isinstance(session, PTYSession)
        assert session.pid > 0
        assert session.cwd == str(tmp_path)
        # The pid must belong to a live process, not be a file descriptor
        # number - see the pty.openpty()/pty.fork() mix-up this replaces.
        assert Path(f"/proc/{session.pid}").exists()
        assert manager.list_sessions()[0]["session_id"] == session.session_id

        assert asyncio.run(manager.write_input(session.session_id, "ping\n")) is True
        assert manager.close_session(session.session_id) is True
        assert manager.list_sessions() == []

    def test_close_unknown_session_returns_false(self):
        assert EnhancedPTYManager().close_session("nope") is False

    def test_read_and_write_unknown_session(self):
        manager = EnhancedPTYManager()
        assert asyncio.run(manager.read_output("nope")) == ""
        assert asyncio.run(manager.write_input("nope", "x")) is False
        assert asyncio.run(manager.resize("nope", 100, 40)) is False

    def test_resize_applies_to_live_session(self, tmp_path: Path):
        manager = EnhancedPTYManager()
        session = manager.create_session(command="/bin/cat", cwd=str(tmp_path))
        try:
            assert asyncio.run(manager.resize(session.session_id, 132, 43)) is True
        finally:
            manager.close_session(session.session_id)


class TestEnhancedSudoManager:
    def test_cache_round_trip_and_ttl(self):
        manager = EnhancedSudoManager()
        assert manager.get_password() is None
        assert manager.is_cached() is False

        manager.set_password("secret")
        assert manager.get_password() == "secret"
        assert manager.is_cached() is True

        manager._last_auth -= 10_000
        assert manager.get_password() is None
        assert manager.is_cached() is False

    def test_clear(self):
        manager = EnhancedSudoManager()
        manager.set_password("secret")
        manager.clear()
        assert manager.get_password() is None


class TestEnhancedShellInitHandler:
    def test_env_passthrough_vars_are_allow_listed(self):
        allowed = EnhancedShellInitHandler.get_env_passthrough_vars()
        assert "PATH" in allowed and "HOME" in allowed
        assert "AWS_SECRET_ACCESS_KEY" not in allowed


# ---------------------------------------------------------------------------
# test_generator
# ---------------------------------------------------------------------------
class TestTestGenerator:
    async def test_generates_tests_for_classes_and_functions(self, tmp_path: Path):
        src = tmp_path / "mod.py"
        src.write_text(
            '"""Mod."""\n\n\nclass Widget:\n    """W."""\n\n'
            "    def run(self):\n        pass\n\n\ndef helper(a, b):\n    return a + b\n"
        )

        tests = await CodeTestGenerator().generate_tests(str(src), str(tmp_path / "out"))
        names = {t.name for t in tests}
        assert "test_widget" in names
        assert "test_helper" in names
        assert all(t.file_path.endswith("test_mod.py") for t in tests)
        assert (tmp_path / "out" / "test_mod.py").exists()

    async def test_missing_source_returns_empty(self, tmp_path: Path):
        assert (
            await CodeTestGenerator().generate_tests(
                str(tmp_path / "nope.py"), str(tmp_path / "out")
            )
            == []
        )

    def test_extract_classes_and_functions(self):
        gen = CodeTestGenerator()
        content = "class A(Base):\n    pass\n\n\ndef f(a):\n    pass\n\n\ndef _g():\n    pass\n"
        assert [c["name"] for c in gen._extract_classes(content)] == ["A"]
        assert [f["name"] for f in gen._extract_functions(content)] == ["f"]

    def test_combine_tests_drops_module_docstrings_and_imports(self):
        gen = CodeTestGenerator()
        combined = gen._combine_tests(
            [
                GeneratedTest(
                    name="a",
                    code='"""D."""\nfrom x import y\ndef test_a(): pass\n',
                    file_path="t.py",
                    test_type="unit",
                )
            ]
        )
        assert combined.startswith('""')
        assert "import pytest" in combined
        assert "def test_a(): pass" in combined
        assert "from x import y" not in combined

    def test_generated_test_defaults(self):
        t = GeneratedTest(name="n", code="c", file_path="f.py", test_type="unit")
        assert t.test_type == "unit"


# ---------------------------------------------------------------------------
# testing
# ---------------------------------------------------------------------------
class _Executor:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def sync_action(self, value: str = "") -> str:
        self.calls.append(f"sync:{value}")
        return f"ok-{value}"

    async def async_action(self, value: str = "") -> str:
        self.calls.append(f"async:{value}")
        return f"ok-{value}"


class TestRunnerBehaviour:
    async def test_run_test_with_sync_executor(self):
        runner = ToolTestRunner()
        runner.add_test(
            "t1", steps=[{"action": "sync_action", "params": {"value": "1"}, "expected": "ok-1"}]
        )
        result = await runner.run_test("t1", _Executor())
        assert result["status"] == "passed"
        assert result["steps"][0]["status"] == "passed"

    async def test_run_test_with_async_executor(self):
        runner = ToolTestRunner()
        runner.add_test(
            "t1", steps=[{"action": "async_action", "params": {"value": "2"}, "expected": "ok-2"}]
        )
        assert (await runner.run_test("t1", _Executor()))["status"] == "passed"

    async def test_unexpected_value_fails_the_step(self):
        runner = ToolTestRunner()
        runner.add_test(
            "t1",
            steps=[
                {"action": "sync_action", "params": {"value": "1"}, "expected": "something-else"}
            ],
        )
        result = await runner.run_test("t1", _Executor())
        assert result["status"] == "failed"
        assert result["steps"][0]["status"] == "failed"

    async def test_unknown_test_returns_error(self):
        assert (await ToolTestRunner().run_test("ghost"))["error"] == "Test 'ghost' not found"

    async def test_step_without_executor_never_fails(self):
        runner = ToolTestRunner()
        runner.add_test("t1", steps=[{"action": "anything"}])
        result = await runner.run_test("t1")
        assert result["steps"][0]["result"] == "No executor for action 'anything'"

    async def test_unknown_action_on_executor(self):
        runner = ToolTestRunner()
        runner.add_test("t1", steps=[{"action": "missing_action"}])
        result = await runner.run_test("t1", _Executor())
        assert "not found" in result["steps"][0]["result"]

    async def test_executor_exception_fails_the_step_only(self):
        class Boom:
            def action(self) -> str:
                raise RuntimeError("kaboom")

        runner = ToolTestRunner()
        runner.add_test("t1", steps=[{"action": "action"}])
        result = await runner.run_test("t1", Boom())
        assert result["steps"][0]["status"] == "failed"
        assert result["steps"][0]["error"] == "kaboom"

    async def test_run_all_and_summary(self):
        runner = ToolTestRunner()
        runner.add_test(
            "pass", steps=[{"action": "sync_action", "params": {"value": "1"}, "expected": "ok-1"}]
        )
        runner.add_test(
            "fail", steps=[{"action": "sync_action", "params": {"value": "1"}, "expected": "nope"}]
        )
        results = await runner.run_all(_Executor())
        assert len(results) == 2
        assert runner.get_summary() == {"total": 2, "passed": 1, "failed": 1}
        assert "✅ pass" in runner.format_report()
        assert "❌ fail" in runner.format_report()

    def test_test_case_defaults(self):
        case = RunnerTestCase(name="n")
        assert case.status == "pending" and case.steps == []


# ---------------------------------------------------------------------------
# todo
# ---------------------------------------------------------------------------
class TestTodoTool:
    def test_add_update_delete(self, tmp_path: Path):
        tool = TodoTool(str(tmp_path / "todos"))
        todo = tool.add("write tests", priority="high")

        assert todo.id.startswith("todo_")
        assert todo.priority == "high"
        assert tool.list_todos()[0]["content"] == "write tests"

        assert tool.update_status(todo.id, "completed") is True
        assert tool.list_todos(status="completed")[0]["status"] == "completed"
        assert tool.delete(todo.id) is True
        assert tool.list_todos() == []

    def test_unknown_id_operations(self, tmp_path: Path):
        tool = TodoTool(str(tmp_path / "todos"))
        assert tool.update_status("nope", "done") is False
        assert tool.delete("nope") is False

    def test_persistence_across_instances(self, tmp_path: Path):
        data_dir = str(tmp_path / "todos")
        first = TodoTool(data_dir)
        todo = first.add("persisted")

        second = TodoTool(data_dir)
        assert [t["content"] for t in second.list_todos()] == ["persisted"]
        assert second.get_summary() == {
            "total": 1,
            "pending": 1,
            "in_progress": 0,
            "completed": 0,
        }
        assert second._todos[todo.id].id == todo.id

    def test_corrupt_store_is_ignored(self, tmp_path: Path):
        data_dir = tmp_path / "todos"
        data_dir.mkdir()
        (data_dir / "todos.json").write_text("{not json")
        assert TodoTool(str(data_dir)).list_todos() == []

    def test_clear_completed(self, tmp_path: Path):
        tool = TodoTool(str(tmp_path / "todos"))
        todo = tool.add("done soon")
        assert tool.clear_completed() == 0
        tool.update_status(todo.id, "completed")
        assert tool.clear_completed() == 1

    def test_todo_item_defaults(self):
        item = TodoItem(id="1", content="c")
        assert item.status == "pending" and item.priority == "medium"


# ---------------------------------------------------------------------------
# translator
# ---------------------------------------------------------------------------
class TestCodeTranslator:
    async def test_python_to_javascript(self):
        translated = await CodeTranslator().translate(
            "def greet(name):\n    print(name)\n    return None\n",
            "python",
            "javascript",
        )
        assert "function greet(name) {" in translated
        assert "console.log(name)" in translated
        assert "null" in translated

    async def test_python_to_typescript(self):
        translated = await CodeTranslator().translate(
            "def greet(name):\n    print(name)\n", "python", "typescript"
        )
        assert "function greet(name): any {" in translated

    async def test_javascript_to_python(self):
        translated = await CodeTranslator().translate(
            "function greet(name) {\n    console.log(name);\n}\n",
            "javascript",
            "python",
        )
        assert "def greet(name):" in translated
        assert "print(name)" in translated

    async def test_unsupported_direction_returns_notice(self):
        out = await CodeTranslator().translate("x", "cobol", "python")
        assert "not supported" in out

    def test_supported_translations_and_rules(self):
        translator = CodeTranslator()
        pairs = {(t["source"], t["target"]) for t in translator.get_supported_translations()}
        assert ("python", "javascript") in pairs
        assert translator.get_rules("python", "javascript")[0]["name"] == "def"

    def test_translation_rule_defaults(self):
        rule = TranslationRule(
            name="n",
            source_lang="a",
            target_lang="b",
            source_pattern="x",
            target_pattern="y",
        )
        assert rule.description == ""


# ---------------------------------------------------------------------------
# webfetch / websearch (loopback HTTP server - no external network)
# ---------------------------------------------------------------------------
class _PageHandler(BaseHTTPRequestHandler):
    payload = b"<html><head><title>Unit</title></head><body><p>Hello</p></body></html>"

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path.startswith("/json"):
            blob = b'{"answer": 42}'
            content_type = "application/json"
        elif self.path.startswith("/big"):
            blob = b"x" * 5000
            content_type = "text/plain"
        else:
            blob = self.payload
            content_type = "text/html"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def web_server():
    server = HTTPServer(("127.0.0.1", 0), _PageHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://localhost:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


class TestWebFetchTool:
    async def test_fetch_html(self, web_server: str):
        result = await WebFetchTool().fetch(f"{web_server}/page", format="html")
        assert result["content_type"] == "html"
        assert "<p>Hello</p>" in result["content"]

    async def test_fetch_text(self, web_server: str):
        result = await WebFetchTool().fetch(f"{web_server}/page")
        assert "Hello" in result["content"]

    async def test_fetch_json(self, web_server: str):
        assert await WebFetchTool().fetch(f"{web_server}/json", format="json") == {
            "content": {"answer": 42}
        }

    async def test_fetch_text_helper(self, web_server: str):
        assert "Hello" in await WebFetchTool().fetch_text(f"{web_server}/page")

    async def test_fetch_json_helper(self, web_server: str):
        assert await WebFetchTool().fetch_json(f"{web_server}/json") == {"answer": 42}

    async def test_max_size_truncates(self, web_server: str):
        tool = WebFetchTool()
        tool.set_max_size(10)
        assert len(await tool.fetch_text(f"{web_server}/big")) == 10

    async def test_unreachable_host_returns_error(self):
        tool = WebFetchTool()
        tool.set_timeout(0.2)
        result = await tool.fetch("http://localhost:1/nothing-listens")
        assert "error" in result

    def test_setters(self):
        tool = WebFetchTool()
        tool.set_timeout(5.5)
        tool.set_max_size(2048)
        assert tool._timeout == 5.5
        assert tool._max_size == 2048


class TestWebSearchTool:
    """tools/websearch.py posts to api.duckduckgo.com - an external boundary."""

    @staticmethod
    def _redirect(monkeypatch: pytest.MonkeyPatch, payload: dict) -> None:
        import httpx

        real_client = httpx.AsyncClient

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.host == "api.duckduckgo.com"
            assert request.url.params["q"] == "bahram"
            return httpx.Response(200, json=payload)

        monkeypatch.setattr(
            httpx,
            "AsyncClient",
            lambda **kwargs: real_client(transport=httpx.MockTransport(handler)),
        )

    async def test_abstract_and_related_topics(self, monkeypatch: pytest.MonkeyPatch):
        self._redirect(
            monkeypatch,
            {
                "Abstract": "An agent framework",
                "Heading": "Bahram",
                "AbstractURL": "https://example.com/bahram",
                "RelatedTopics": [
                    {"Text": "Topic one", "FirstURL": "https://example.com/1"},
                    {"Text": "Topic two", "FirstURL": "https://example.com/2"},
                    {"Topics": [{"Text": "nested"}]},
                ],
            },
        )
        results = await WebSearchTool().search("bahram")

        assert results[0] == {
            "title": "Bahram",
            "content": "An agent framework",
            "url": "https://example.com/bahram",
        }
        assert len(results) == 3

    async def test_empty_abstract_still_returns_topics(self, monkeypatch: pytest.MonkeyPatch):
        self._redirect(
            monkeypatch,
            {"RelatedTopics": [{"Text": "only one", "FirstURL": "https://e/1"}]},
        )
        results = await WebSearchTool().search("bahram", num_results=1)
        assert len(results) == 1

    async def test_http_error_is_reported(self, monkeypatch: pytest.MonkeyPatch):
        import httpx

        real_client = httpx.AsyncClient
        monkeypatch.setattr(
            httpx,
            "AsyncClient",
            lambda **kwargs: real_client(
                transport=httpx.MockTransport(lambda r: httpx.Response(503))
            ),
        )
        results = await WebSearchTool().search("bahram")
        assert "HTTP 503" in results[0]["error"]

    async def test_summarize_renders_numbered_results(self, monkeypatch: pytest.MonkeyPatch):
        self._redirect(
            monkeypatch,
            {
                "Abstract": "summary",
                "Heading": "H",
                "AbstractURL": "https://e",
                "RelatedTopics": [],
            },
        )
        text = await WebSearchTool().search_and_summarize("bahram")
        assert text.startswith("Search results for: bahram")
        assert "1. H" in text
        assert "URL: https://e" in text

    async def test_summarize_handles_errors(self, monkeypatch: pytest.MonkeyPatch):
        self._redirect(monkeypatch, {"RelatedTopics": []})
        assert "No results found" in await WebSearchTool().search_and_summarize("bahram")

    def test_setters(self):
        tool = WebSearchTool()
        tool.set_search_engine("bing")
        tool.set_max_results(3)
        assert tool._search_engine == "bing"
        assert tool._max_results == 3
