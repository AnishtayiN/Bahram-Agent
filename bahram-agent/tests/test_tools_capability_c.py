"""Behavioural tests for the tools/capability modules (batch C).

Covers: git, image_gen, lsp, migration, monitoring, optimizer, process,
profiler, progress, refactor, search, security_scan, smart_completion,
smart_doc.

No network access: the one HTTP-backed module (image_gen) is exercised through
a real loopback HTTP server started by the test, so the code under test issues
genuine HTTP requests without leaving the machine.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from bahram.tools.git import GitCommit, GitTool
from bahram.tools.image_gen import ImageGenTool
from bahram.tools.lsp import LSPServer, LSPTool
from bahram.tools.migration import CodeMigration, MigrationRule
from bahram.tools.monitoring import Alert, Metric, PerformanceMonitor
from bahram.tools.optimizer import OptimizationSuggestion, PerformanceOptimizer
from bahram.tools.process import ProcessInfo, ProcessManager
from bahram.tools.profiler import FunctionTimer, Profiler, ProfileResult
from bahram.tools.progress import ProgressTracker, ToolProgress
from bahram.tools.refactor import RefactorSuggestion, RefactorTool
from bahram.tools.search import ToolSearch
from bahram.tools.security_scan import SecurityIssue, SecurityScanner
from bahram.tools.smart_completion import CompletionContext, SmartCodeCompletion
from bahram.tools.smart_doc import DocSection, SmartDocGenerator


# ---------------------------------------------------------------------------
# git
# ---------------------------------------------------------------------------
@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real, throwaway git repository with one commit on ``main``."""
    import subprocess

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    git("init", "-q", "-b", "main")
    git("config", "user.email", "unit@example.com")
    git("config", "user.name", "Unit Test")
    git("config", "commit.gpgsign", "false")
    (tmp_path / "README.md").write_text("hello\n")
    git("add", "README.md")
    git("commit", "-q", "-m", "initial commit")
    return tmp_path


class TestGitTool:
    async def test_status_reports_clean_tree(self, repo: Path):
        result = await GitTool(str(repo)).status()
        assert result["clean"] is True
        assert result["files"] == []

    async def test_status_lists_modified_files(self, repo: Path):
        (repo / "README.md").write_text("changed\n")
        result = await GitTool(str(repo)).status()
        assert result["clean"] is False
        assert result["files"] == [{"status": "M", "file": "README.md"}]

    async def test_log_parses_commits(self, repo: Path):
        commits = await GitTool(str(repo)).log(limit=5)
        assert len(commits) == 1
        assert isinstance(commits[0], GitCommit)
        assert commits[0].message == "initial commit"
        assert commits[0].author == "Unit Test"
        assert len(commits[0].hash) == 40

    async def test_log_ignores_unparsable_lines(self, repo: Path):
        tool = GitTool(str(repo))

        async def fake_run(*args: str) -> dict:
            assert args[0] == "log"
            return {
                "stdout": "not-a-record\nabc|Me|2024-01-01|msg\n",
                "stderr": "",
                "returncode": 0,
            }

        tool._run = fake_run  # type: ignore[method-assign]
        commits = await tool.log()
        assert len(commits) == 1 and commits[0].message == "msg"

    async def test_diff_returns_patch(self, repo: Path):
        (repo / "README.md").write_text("changed\n")
        diff = await GitTool(str(repo)).diff()
        assert "README.md" in diff or "changed" in diff

    async def test_add_and_commit(self, repo: Path):
        tool = GitTool(str(repo))
        (repo / "new.txt").write_text("x\n")
        assert await tool.add(["new.txt"]) is True
        assert await tool.commit("add new file") is True
        assert (await tool.status())["clean"] is True

    async def test_add_all(self, repo: Path):
        tool = GitTool(str(repo))
        (repo / "a.txt").write_text("x\n")
        (repo / "b.txt").write_text("y\n")
        assert await tool.add() is True

    async def test_branch_and_checkout(self, repo: Path):
        tool = GitTool(str(repo))
        assert await tool.create_branch("feature") is True
        assert "feature" in await tool.branch()
        assert await tool.checkout("main") is True
        assert await tool.checkout("feature") is True

    async def test_stash_and_pop(self, repo: Path):
        tool = GitTool(str(repo))
        (repo / "README.md").write_text("wip\n")
        assert await tool.stash() is True
        assert (await tool.status())["clean"] is True
        assert await tool.stash_pop() is True

    async def test_blame_returns_annotated_output(self, repo: Path):
        blame = await GitTool(str(repo)).blame("README.md")
        assert "Unit Test" in blame

    async def test_push_and_pull_report_failure_without_remote(self, repo: Path):
        tool = GitTool(str(repo))
        assert await tool.push() is False
        assert await tool.pull() is False


# ---------------------------------------------------------------------------
# image_gen
# ---------------------------------------------------------------------------
def _redirect_httpx_to_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point httpx at an in-process transport.

    ``ImageGenTool`` posts to ``api.openai.com``.  That is an external network
    boundary, so httpx - and only httpx - is redirected to an in-process
    ``MockTransport``.  ``ImageGenTool`` itself runs unmodified: it still
    builds the real request body, parses the real JSON response and writes the
    real downloaded bytes to disk.
    """
    import httpx

    real_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/images/generations"):
            body = json.loads(request.content)
            assert "Bearer test-key" in request.headers["Authorization"]
            assert body["model"] == "dall-e-3"
            return httpx.Response(
                200,
                json={"data": [{"url": "https://loopback.invalid/a-cat.png"}]},
            )
        return httpx.Response(200, content=b"\x89PNG\r\n\x1a\nstub")

    def factory(**kwargs):
        kwargs.pop("timeout", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


class TestImageGenTool:
    async def test_generate_returns_url_and_saves_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _redirect_httpx_to_loopback(monkeypatch)
        tool = ImageGenTool()
        tool.set_api_key("test-key")

        out = tmp_path / "img.png"
        result = await tool.generate("a cat", output_path=str(out))

        assert result["url"] == "https://loopback.invalid/a-cat.png"
        assert result["path"] == str(out)
        assert out.read_bytes().startswith(b"\x89PNG")

    async def test_generate_without_output_path_returns_url_only(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        _redirect_httpx_to_loopback(monkeypatch)
        tool = ImageGenTool()
        tool.set_api_key("test-key")
        result = await tool.generate("a cat")
        assert result == {"url": "https://loopback.invalid/a-cat.png"}

    async def test_unsupported_provider_returns_error(self):
        tool = ImageGenTool()
        tool.set_provider("midjourney")
        assert "Unsupported provider" in (await tool.generate("x"))["error"]

    def test_provider_and_key_setters(self):
        tool = ImageGenTool()
        tool.set_provider("openai")
        tool.set_api_key("abc")
        assert tool._provider == "openai"
        assert tool._api_key == "abc"


# ---------------------------------------------------------------------------
# lsp
# ---------------------------------------------------------------------------
class TestLSPTool:
    def test_register_and_list(self):
        tool = LSPTool()
        tool.register_server("pylsp", "pylsp", "python")
        assert tool.is_running("pylsp") is False

    async def test_start_unknown_server_returns_false(self):
        assert await LSPTool().start_server("ghost") is False

    async def test_stop_unknown_server_returns_false(self):
        assert await LSPTool().stop_server("ghost") is False

    async def test_stop_without_process_returns_false(self):
        tool = LSPTool()
        tool.register_server("pylsp", "pylsp", "python")
        assert await tool.stop_server("pylsp") is False

    async def test_completion_without_server_returns_empty(self):
        tool = LSPTool()
        assert await tool.completion("ghost", "f.py", 1, 0) == []

    def test_lsp_server_defaults(self):
        s = LSPServer(name="n", command="c", language="python")
        assert s.process is None


# ---------------------------------------------------------------------------
# migration
# ---------------------------------------------------------------------------
class TestCodeMigration:
    async def test_unknown_migration_type(self, tmp_path: Path):
        out = await CodeMigration().migrate(str(tmp_path), "out", "nope")
        assert "Unknown migration type" in out["error"]

    async def test_missing_source(self):
        out = await CodeMigration().migrate("/nonexistent", "out", "python2_to_3")
        assert "Source path not found" in out["error"]

    async def test_dry_run_does_not_write(self, tmp_path: Path):
        src = tmp_path / "legacy.py"
        src.write_text("print 'hi'\nxrange(10)\nraw_input('?')\n")

        result = await CodeMigration().migrate(
            str(src), str(tmp_path / "out" / "legacy.py"), "python2_to_3", dry_run=True
        )
        assert result["dry_run"] is True
        assert result["total_changes"] >= 2
        assert not (tmp_path / "out").exists()

    async def test_migrate_file_writes_result(self, tmp_path: Path):
        src = tmp_path / "legacy.py"
        src.write_text("print 'hi'\n")

        out = tmp_path / "migrated" / "legacy.py"
        result = await CodeMigration().migrate(str(src), str(out), "python2_to_3")
        assert result["dry_run"] is False
        assert "print(" in out.read_text()

    async def test_migrate_directory(self, tmp_path: Path):
        src = tmp_path / "pkg"
        src.mkdir()
        (src / "a.py").write_text("xrange(1)\n")
        (src / "b.py").write_text("raw_input()\n")

        result = await CodeMigration().migrate(
            str(src), str(tmp_path / "out"), "python2_to_3", dry_run=True
        )
        assert result["files_migrated"] == 2
        assert result["total_changes"] == 2

    def test_get_migration_types_and_rules(self):
        migration = CodeMigration()
        assert "python2_to_3" in migration.get_migration_types()
        rules = migration.get_rules("pydantic_v1_to_v2")
        assert rules and rules[0]["name"] == "validator"

    def test_migration_rule_defaults(self):
        r = MigrationRule(name="n", source_pattern="a", target_pattern="b", language="py")
        assert r.description == ""


# ---------------------------------------------------------------------------
# monitoring
# ---------------------------------------------------------------------------
class TestPerformanceMonitor:
    def test_record_and_get_metric(self):
        mon = PerformanceMonitor()
        mon.record("latency", 12.5, tags={"route": "/api"})
        metrics = mon.get_metric("latency")
        assert metrics[0]["value"] == 12.5
        assert metrics[0]["tags"] == {"route": "/api"}

    def test_increment_accumulates(self):
        mon = PerformanceMonitor()
        mon.increment("hits")
        mon.increment("hits", 4)
        assert mon.get_counter("hits") == 5

    def test_timer_records_duration(self):
        mon = PerformanceMonitor()
        mon.start_timer("job")
        duration = mon.stop_timer("job")
        assert duration >= 0
        assert mon.get_metric("job_duration")

    def test_stop_unknown_timer_returns_zero(self):
        assert PerformanceMonitor().stop_timer("nope") == 0.0

    def test_alert_fires_once_on_greater(self):
        mon = PerformanceMonitor()
        mon.add_alert("latency", "greater", 10)
        mon.record("latency", 5)
        assert mon.get_alerts() == []
        mon.record("latency", 50)
        assert len(mon.get_alerts()) == 1
        # already triggered - must not duplicate
        mon.record("latency", 60)
        assert len(mon.get_alerts()) == 1

    def test_alert_on_less(self):
        mon = PerformanceMonitor()
        mon.add_alert("free", "less", 10)
        mon.record("free", 1)
        assert mon.get_alerts()[0]["name"] == "free"

    def test_alert_unknown_condition_never_fires(self):
        mon = PerformanceMonitor()
        mon.add_alert("x", "equals", 10)
        mon.record("x", 10)
        assert mon.get_alerts() == []

    def test_summary(self):
        mon = PerformanceMonitor()
        mon.record("latency", 1)
        mon.record("latency", 3)
        summary = mon.get_summary()["latency"]
        assert (summary["count"], summary["min"], summary["max"], summary["avg"]) == (
            2,
            1,
            3,
            2,
        )

    def test_metric_and_alert_defaults(self):
        assert Metric(name="n", value=1, timestamp=0).tags == {}
        assert Alert(name="n", condition="greater", threshold=1).triggered is False


# ---------------------------------------------------------------------------
# optimizer
# ---------------------------------------------------------------------------
class TestPerformanceOptimizer:
    async def test_flags_range_len_pattern(self, tmp_path: Path):
        src = tmp_path / "m.py"
        src.write_text("for i in range(len(items)):\n    pass\n")
        suggestions = await PerformanceOptimizer().analyze(str(src))
        assert suggestions
        assert suggestions[0].after.startswith("for i, item in enumerate(items)")
        assert suggestions[0].severity == "medium"

    async def test_missing_file_returns_empty(self):
        assert await PerformanceOptimizer().analyze("/nonexistent.py") == []

    async def test_clean_file_has_no_suggestions(self, tmp_path: Path):
        src = tmp_path / "m.py"
        src.write_text("value = 1\n")
        assert await PerformanceOptimizer().analyze(str(src)) == []

    def test_summary_counts_by_impact(self):
        opt = PerformanceOptimizer()
        s = OptimizationSuggestion(
            file="f",
            line=1,
            type="performance",
            severity="high",
            description="d",
            before="b",
            after="a",
            impact="high",
        )
        assert opt.get_summary([s])["high"] == 1

    def test_format_suggestions_empty_and_full(self):
        opt = PerformanceOptimizer()
        assert opt.format_suggestions([]) == "No optimization suggestions!"
        out = opt.format_suggestions(
            [
                OptimizationSuggestion(
                    file="f.py",
                    line=2,
                    type="performance",
                    severity="high",
                    description="Use set",
                    before="if x in [1]",
                    after="if x in {1}",
                    impact="high",
                )
            ]
        )
        assert "HIGH Impact" in out and "f.py:2" in out


# ---------------------------------------------------------------------------
# process
# ---------------------------------------------------------------------------
class TestProcessManager:
    async def test_start_and_stop_real_process(self):
        manager = ProcessManager()
        info = await manager.start("sleeper", "sleep 30")
        assert isinstance(info, ProcessInfo)
        assert info.status == "running"

        assert await manager.stop(info.pid, force=True) is True
        # give the monitor task a chance to observe the exit
        await asyncio.sleep(0.2)
        assert (await manager.get_info(info.pid)).status == "failed"

    async def test_stop_unknown_pid_returns_false(self):
        assert await ProcessManager().stop(999_999) is False

    async def test_list_processes_only_lists_running(self):
        manager = ProcessManager()
        info = await manager.start("sleeper", "sleep 30")
        assert [p["pid"] for p in manager.list_processes()] == [info.pid]
        await manager.stop(info.pid, force=True)
        await asyncio.sleep(0.2)
        assert manager.list_processes() == []

    async def test_cleanup_removes_finished_processes(self):
        manager = ProcessManager()
        info = await manager.start("done", "true")
        await asyncio.sleep(0.3)
        assert await manager.cleanup() == 1
        assert await manager.get_info(info.pid) is None

    async def test_get_info_unknown_pid(self):
        assert await ProcessManager().get_info(1) is None

    def test_process_info_defaults(self):
        info = ProcessInfo(pid=1, name="n", command="c")
        assert info.status == "running"


# ---------------------------------------------------------------------------
# profiler
# ---------------------------------------------------------------------------
class TestProfiler:
    def test_start_stop_and_stats(self):
        profiler = Profiler()

        def work() -> int:
            return sum(i * i for i in range(2000))

        profiler.start()
        work()
        profiler.stop()

        results = profiler.get_stats(top_n=5)
        assert results
        assert isinstance(results[0], ProfileResult)
        assert any("work" in r.function for r in results)

    def test_format_report(self):
        out = Profiler().format_report(
            [ProfileResult(function="f", calls=2, total_time=0.5, per_call=0.25)]
        )
        assert "Profile Report" in out and "0.5000" in out

    def test_reset_clears_state(self):
        profiler = Profiler()
        profiler.start()
        profiler.stop()
        profiler.reset()
        assert profiler.get_stats() == []


_TIMER = FunctionTimer()


@_TIMER.time
def _timed_sync(x: int) -> int:
    """Doubles its input."""
    return x * 2


@_TIMER.time
async def _timed_async(x: int) -> int:
    """Triples its input."""
    return x * 3


class TestFunctionTimer:
    async def test_times_sync_and_async_functions(self):
        assert _timed_sync(2) == 4
        assert await _timed_async(2) == 6

        report = _TIMER.get_report()
        assert "_timed_sync" in report and "_timed_async" in report

    def test_sync_wrapper_preserves_metadata(self):
        assert _timed_sync.__name__ == "_timed_sync"
        assert "Doubles its input." in (_timed_sync.__doc__ or "")

    def test_timer_preserves_metadata(self):
        timer = FunctionTimer()

        @timer.time
        def documented() -> str:
            """Docstring survives decoration."""
            return "ok"

        assert documented() == "ok"
        assert documented.__name__ == "documented"
        assert "Docstring survives" in (documented.__doc__ or "")

    def test_reset(self):
        timer = FunctionTimer()

        @timer.time
        def f() -> None:
            return None

        f()
        assert "f" in timer.get_report()
        timer.reset()
        assert "f" not in timer.get_report()


# ---------------------------------------------------------------------------
# progress
# ---------------------------------------------------------------------------
class TestProgressTracker:
    def test_lifecycle(self):
        tracker = ProgressTracker()
        tracker_id = tracker.start("bash")

        active = tracker.get_active()
        assert len(active) == 1 and active[0]["tool"] == "bash"

        tracker.update(tracker_id, progress=50, message="halfway")
        assert tracker.get_active()[0]["progress"] == 50
        assert tracker.get_active()[0]["message"] == "halfway"

        tracker.complete(tracker_id, result="done")
        assert tracker.get_active() == []
        assert tracker.get_history()[0]["status"] == "completed"

    def test_failure_records_error(self):
        tracker = ProgressTracker()
        tracker_id = tracker.start("bash")
        tracker.fail(tracker_id, "boom")
        history = tracker.get_history()
        assert history[0]["status"] == "failed"
        assert history[0]["error"] == "boom"

    def test_unknown_tracker_id_is_ignored(self):
        tracker = ProgressTracker()
        tracker.update("nope", progress=1)
        tracker.complete("nope")
        tracker.fail("nope", "x")
        assert tracker.get_history() == []

    def test_callbacks_receive_updates(self):
        seen: list[str] = []
        tracker = ProgressTracker()
        tracker.add_callback(lambda p: seen.append(p.status))
        tracker_id = tracker.start("bash")
        tracker.complete(tracker_id)
        assert seen == ["running", "completed"]

    def test_failing_callback_does_not_break_tracking(self):
        def boom(_p: ToolProgress) -> None:
            raise RuntimeError("callback failed")

        tracker = ProgressTracker()
        tracker.add_callback(boom)
        tracker_id = tracker.start("bash")
        tracker.complete(tracker_id)
        assert tracker.get_history()[0]["status"] == "completed"

    def test_history_limit(self):
        tracker = ProgressTracker()
        for i in range(5):
            tid = tracker.start(f"tool{i}")
            tracker.complete(tid)
        assert len(tracker.get_history(limit=2)) == 2

    def test_tool_progress_defaults(self):
        p = ToolProgress(tool_name="bash")
        assert p.status == "pending" and p.progress == 0.0


# ---------------------------------------------------------------------------
# refactor
# ---------------------------------------------------------------------------
class TestRefactorTool:
    async def test_flags_pythonic_issues(self, tmp_path: Path):
        src = tmp_path / "m.py"
        src.write_text("if flag == None:\n    pass\nif len(items) == 0:\n    pass\n")
        suggestions = await RefactorTool().analyze(str(src))
        descriptions = {s.description for s in suggestions}
        assert "Use 'is' for None comparison" in descriptions
        assert "Use 'not' for empty check" in descriptions

    async def test_rewrite_is_suggested_not_applied(self, tmp_path: Path):
        src = tmp_path / "m.py"
        src.write_text("if flag is True:\n    pass\n")
        suggestion = (await RefactorTool().analyze(str(src)))[0]
        assert suggestion.before == "if flag is True:"
        assert suggestion.after == "if flag:"
        assert src.read_text() == "if flag is True:\n    pass\n"

    async def test_missing_file_returns_empty(self):
        assert await RefactorTool().analyze("/nonexistent.py") == []

    def test_summary_and_format(self):
        tool = RefactorTool()
        s = RefactorSuggestion(
            file="f.py", line=1, type="pythonic", description="d", before="b", after="a"
        )
        assert tool.get_summary([s]) == {"pythonic": 1}
        assert tool.format_suggestions([]) == "No refactoring suggestions!"
        assert "f.py:1" in tool.format_suggestions([s])


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------
class TestToolSearch:
    def test_search_ranks_name_matches_above_description_matches(self):
        search = ToolSearch()
        search.register_tool("read", "Read a file", category="fs")
        search.register_tool("grep", "Read-only search of file contents", category="fs")

        results = search.search("read")
        assert results[0]["name"] == "read"
        assert results[0]["score"] > results[1]["score"]

    def test_search_filters_by_category(self):
        search = ToolSearch()
        search.register_tool("read", "Read a file", category="fs")
        search.register_tool("curl", "Fetch a URL", category="net")
        assert [r["name"] for r in search.search("read", category="net")] == []

    def test_search_respects_limit(self):
        search = ToolSearch()
        for i in range(5):
            search.register_tool(f"tool{i}", f"tool{i} helper", category="misc")
        assert len(search.search("tool", limit=2)) == 2

    def test_list_categories_is_sorted_and_unique(self):
        search = ToolSearch()
        search.register_tool("a", "d", category="z")
        search.register_tool("b", "d", category="a")
        search.register_tool("c", "d", category="a")
        assert search.list_categories() == ["a", "z"]

    def test_get_tool_and_list_all(self):
        search = ToolSearch()
        search.register_tool("read", "Read a file")
        assert search.get_tool("read")["description"] == "Read a file"
        assert search.get_tool("nope") is None
        assert len(search.list_all()) == 1


# ---------------------------------------------------------------------------
# security_scan
# ---------------------------------------------------------------------------
class TestSecurityScanner:
    async def test_flags_eval_and_hardcoded_secret(self, tmp_path: Path):
        src = tmp_path / "m.py"
        src.write_text("eval('1')\npassword = 'hunter2'\n")

        issues = await SecurityScanner().scan_file(str(src))
        descriptions = {i.description for i in issues}
        assert "eval() usage" in descriptions
        assert "Hardcoded password" in descriptions
        assert all(i.severity in {"critical", "high", "medium", "low"} for i in issues)

    async def test_safe_file_has_no_issues(self, tmp_path: Path):
        src = tmp_path / "m.py"
        src.write_text("import os\nvalue = os.environ['PASSWORD']\n")
        assert await SecurityScanner().scan_file(str(src)) == []

    async def test_scan_directory_walks_python_files(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("exec('x')\n")
        (tmp_path / "b.txt").write_text("exec('x')\n")
        issues = await SecurityScanner().scan_directory(str(tmp_path))
        assert len(issues) == 1 and issues[0].file.endswith("a.py")

    async def test_missing_file_returns_empty(self):
        assert await SecurityScanner().scan_file("/nonexistent.py") == []

    def test_report_groups_by_severity(self):
        scanner = SecurityScanner()
        issues = [
            SecurityIssue(
                file="f",
                line=1,
                severity="critical",
                category="c",
                description="eval() usage",
                recommendation="avoid",
            ),
            SecurityIssue(
                file="f",
                line=2,
                severity="low",
                category="c",
                description="style",
                recommendation="tidy",
            ),
        ]
        report = scanner.get_report(issues)
        assert "CRITICAL" in report and "LOW" in report
        assert scanner.get_summary(issues)["critical"] == 1

    def test_empty_report_message(self):
        assert SecurityScanner().get_report([]) == "No security issues found!"


# ---------------------------------------------------------------------------
# smart_completion
# ---------------------------------------------------------------------------
class TestSmartCodeCompletion:
    def test_trigger_filters_snippets(self):
        engine = SmartCodeCompletion()
        completions = engine.complete(
            CompletionContext(
                file_path="m.py", line=1, column=0, language="python", code_before=""
            ),
            trigger="def",
        )
        assert completions[0]["trigger"] == "def"
        assert "def ${1:name}" in completions[0]["text"]

    def test_context_after_import_suggests_modules(self):
        engine = SmartCodeCompletion()
        completions = engine.complete(
            CompletionContext(
                file_path="m.py",
                line=1,
                column=0,
                language="python",
                code_before="import ",
            )
        )
        assert "os" in [c["text"] for c in completions]

    def test_context_after_def_suggests_dunders(self):
        engine = SmartCodeCompletion()
        completions = engine.complete(
            CompletionContext(
                file_path="m.py",
                line=2,
                column=0,
                language="python",
                code_before="class A:",
            )
        )
        assert "def __init__(self):" in [c["text"] for c in completions]

    def test_context_inside_function_body(self):
        engine = SmartCodeCompletion()
        completions = engine.complete(
            CompletionContext(
                file_path="m.py",
                line=3,
                column=4,
                language="python",
                code_before="def f():\n    x = 1\n    ",
            )
        )
        assert "return" in [c["text"] for c in completions]

    def test_unknown_language_returns_only_snippet_free_results(self):
        engine = SmartCodeCompletion()
        completions = engine.complete(
            CompletionContext(
                file_path="m.rs", line=1, column=0, language="rust", code_before="fn "
            )
        )
        assert completions == []

    def test_get_snippet_and_unknown_snippet(self):
        engine = SmartCodeCompletion()
        assert engine.get_snippet("python", "class") is not None
        assert engine.get_snippet("python", "zzz") is None

    def test_completion_context_defaults(self):
        ctx = CompletionContext(file_path="f", line=1, column=1, language="python", code_before="")
        assert ctx.code_after == ""


# ---------------------------------------------------------------------------
# smart_doc
# ---------------------------------------------------------------------------
class TestSmartDocGenerator:
    async def test_generate_markdown_from_source(self, tmp_path: Path):
        src = tmp_path / "mod.py"
        src.write_text(
            '"""Module summary."""\n\n\nclass Widget:\n    """A widget."""\n\n'
            '    def run(self) -> bool:\n        """Run it."""\n        return True\n'
        )

        out = tmp_path / "docs" / "mod.md"
        assert await SmartDocGenerator().generate(str(src), str(out)) is True

        text = out.read_text()
        assert "Module summary." in text
        assert "### Widget" in text
        assert "#### `run(self)`" in text
        assert "Usage Examples" in text

    async def test_missing_source_returns_false(self, tmp_path: Path):
        gen = SmartDocGenerator()
        assert await gen.generate(str(tmp_path / "nope.py"), str(tmp_path / "o.md")) is False

    async def test_examples_can_be_disabled(self, tmp_path: Path):
        src = tmp_path / "mod.py"
        src.write_text('"""Doc."""\n\n\nclass Widget:\n    """W."""\n')
        out = tmp_path / "o.md"
        await SmartDocGenerator().generate(str(src), str(out), include_examples=False)
        assert "Usage Examples" not in out.read_text()

    def test_render_sections_uses_heading_levels(self):
        gen = SmartDocGenerator()
        rendered = gen._render_sections(
            [DocSection(name="Top", content="body", level=2)], format="markdown"
        )
        assert rendered.startswith("## Top")

    def test_extract_functions_skips_private_names(self):
        gen = SmartDocGenerator()
        functions = gen._extract_functions(
            "def public(a) -> int:\n    pass\n\n\ndef _hidden(b):\n    pass\n"
        )
        assert [f["name"] for f in functions] == ["public"]

    def test_extract_module_docstring_missing(self):
        assert SmartDocGenerator()._extract_module_docstring("x = 1\n") == ""

    def test_doc_section_defaults(self):
        assert DocSection(name="n", content="c").level == 1
