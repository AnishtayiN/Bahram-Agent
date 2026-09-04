"""Behavioural tests for the tools/capability modules (batch A).

Covers: ai_generator, annotations, api_generator, autocomplete, bg_notify,
browser, clarify, code_review, code_search.

These modules are engineering helpers that live next to the LLM-callable
tools.  They are exercised here with real filesystem fixtures and real
subprocesses - no network and no mocking of project code.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from bahram.tools.ai_generator import AICodeGenerator, GeneratedFile
from bahram.tools.annotations import AnnotationManager, ToolAnnotation
from bahram.tools.api_generator import APIEndpoint, APIGenerator
from bahram.tools.autocomplete import AutoComplete, Completion
from bahram.tools.bg_notify import BackgroundNotifier, BackgroundTask
from bahram.tools.browser import BrowserState, BrowserTool
from bahram.tools.clarify import ClarifyTool
from bahram.tools.code_review import CodeIssue, CodeReviewTool
from bahram.tools.code_search import CodeSearchEngine, SearchResult


# ---------------------------------------------------------------------------
# ai_generator
# ---------------------------------------------------------------------------
class TestAICodeGenerator:
    async def test_generate_fastapi_writes_every_template_file(self, tmp_path: Path):
        gen = AICodeGenerator()
        out = str(tmp_path / "out")
        files = await gen.generate("A REST service", framework="fastapi", output_dir=out)

        assert [f.path for f in files] == [
            "main.py",
            "requirements.txt",
            "Dockerfile",
            "README.md",
        ]
        for f in files:
            assert (Path(out) / f.path).exists()
            assert (Path(out) / f.path).read_text() == f.content
        # requirements.txt is the only generator with real content today
        req = next(f for f in files if f.path == "requirements.txt")
        assert "fastapi" in req.content
        assert req.language == "text"

    async def test_generate_react_uses_typescript_branch(self, tmp_path: Path):
        gen = AICodeGenerator()
        files = await gen.generate("app", framework="react", output_dir=str(tmp_path))
        assert {f.language for f in files} == {"typescript", "json", "markdown"}

    async def test_generate_cli_branch(self, tmp_path: Path):
        gen = AICodeGenerator()
        files = await gen.generate("cli", framework="cli", output_dir=str(tmp_path))
        req = next(f for f in files if f.path == "requirements.txt")
        assert "click" in req.content

    async def test_unknown_framework_returns_empty_list(self, tmp_path: Path):
        gen = AICodeGenerator()
        assert await gen.generate("x", framework="nope", output_dir=str(tmp_path)) == []

    def test_generated_file_dataclass_defaults(self):
        f = GeneratedFile(path="a.py", content="x", language="python")
        assert f.description == ""


# ---------------------------------------------------------------------------
# annotations
# ---------------------------------------------------------------------------
class TestAnnotationManager:
    def test_add_and_read_back(self):
        mgr = AnnotationManager()
        mgr.add_annotation("tc1", "exit_code", 0, metadata={"note": "ok"})

        anns = mgr.get_annotations("tc1")
        assert len(anns) == 1
        assert anns[0]["key"] == "exit_code"
        assert anns[0]["value"] == 0
        assert anns[0]["timestamp"] > 0

    def test_get_annotation_returns_latest_value(self):
        mgr = AnnotationManager()
        mgr.add_annotation("tc1", "exit_code", 1)
        mgr.add_annotation("tc1", "exit_code", 2)
        assert mgr.get_annotation("tc1", "exit_code") == 2

    def test_missing_key_and_missing_call(self):
        mgr = AnnotationManager()
        assert mgr.get_annotation("nope", "exit_code") is None
        assert mgr.get_annotations("nope") == []
        mgr.add_annotation("tc1", "a", 1)
        assert mgr.get_annotation("tc1", "b") is None

    def test_clear_annotations(self):
        mgr = AnnotationManager()
        mgr.add_annotation("tc1", "a", 1)
        mgr.clear_annotations("tc1")
        assert mgr.get_all_annotations() == {}

    def test_convenience_setters(self):
        mgr = AnnotationManager()
        mgr.set_exit_code("tc1", 3)
        mgr.set_utf16_transcoded("tc1", True)
        mgr.set_output_size("tc1", 42)
        assert mgr.get_annotation("tc1", "exit_code") == 3
        assert mgr.get_annotation("tc1", "utf16_transcoded") is True
        assert mgr.get_annotation("tc1", "output_size") == 42
        assert set(mgr.get_all_annotations()) == {"tc1"}

    def test_tool_annotation_defaults(self):
        a = ToolAnnotation(key="k", value="v")
        assert a.timestamp == 0.0
        assert a.metadata == {}


# ---------------------------------------------------------------------------
# api_generator
# ---------------------------------------------------------------------------
class TestAPIGenerator:
    def test_generate_unknown_framework_reports_error(self):
        gen = APIGenerator()
        assert "Unsupported framework" in gen.generate(framework="rails")

    def test_generate_known_framework_returns_template(self):
        gen = APIGenerator()
        for framework in ("fastapi", "flask", "express"):
            assert isinstance(gen.generate(framework=framework), str)

    def test_add_endpoint_and_openapi(self):
        gen = APIGenerator()
        gen.add_endpoint(
            APIEndpoint(
                path="/items",
                method="GET",
                handler="list_items",
                description="List items",
                parameters=[{"name": "limit", "type": "integer", "required": True}],
            )
        )
        gen.add_endpoint(APIEndpoint(path="/items", method="POST", handler="create_item"))
        spec = gen.generate_openapi()

        assert spec["openapi"] == "3.0.0"
        assert set(spec["paths"]["/items"]) == {"get", "post"}
        assert spec["paths"]["/items"]["get"]["parameters"][0]["required"] is True
        assert spec["paths"]["/items"]["get"]["summary"] == "List items"

    def test_get_params_required_and_optional(self):
        gen = APIGenerator()
        ep = APIEndpoint(
            path="/x",
            method="GET",
            handler="h",
            parameters=[
                {"name": "a", "type": "int", "required": True},
                {"name": "b", "required": False, "default": "5"},
            ],
        )
        assert gen._get_params(ep) == "a: int, b: str = 5"


# ---------------------------------------------------------------------------
# autocomplete
# ---------------------------------------------------------------------------
class TestAutoComplete:
    def test_complete_python_keywords(self):
        ac = AutoComplete()
        got = ac.complete("de", language="python")
        assert "def " in [c.text for c in got]

    def test_complete_is_case_insensitive(self):
        ac = AutoComplete()
        assert ac.complete("DEF", language="python")

    def test_complete_unknown_language_returns_only_history(self):
        ac = AutoComplete()
        ac.add_to_history("somePreviouslyTypedCommand")
        got = ac.complete("some", language="cobol")
        assert [c.text for c in got] == ["somePreviouslyTypedCommand"]

    def test_history_is_deduplicated_and_bounded(self):
        ac = AutoComplete()
        ac.add_to_history("dup")
        ac.add_to_history("dup")
        assert ac._history == ["dup"]
        for i in range(1005):
            ac.add_to_history(f"cmd{i}")
        assert len(ac._history) == 1000

    def test_completions_are_unique_and_capped_at_ten(self):
        ac = AutoComplete()
        got = ac.complete("", language="python")
        assert len(got) <= 10
        assert len({c.text for c in got}) == len(got)

    def test_complete_command_uses_bash_patterns(self):
        ac = AutoComplete()
        assert "git" in [c.text for c in ac.complete_command("gi")]

    def test_complete_import(self):
        ac = AutoComplete()
        assert "json" in [c.text for c in ac.complete_import("js")]
        # dotted input matches against the last component
        assert "os" in [c.text for c in ac.complete_import("mod.os")]

    def test_complete_function(self):
        ac = AutoComplete()
        assert "len()" in [c.text for c in ac.complete_function("len")]

    def test_get_suggestions_returns_plain_strings(self):
        ac = AutoComplete()
        assert all(isinstance(s, str) for s in ac.get_suggestions("de"))

    def test_completion_dataclass_defaults(self):
        c = Completion(text="x")
        assert (c.description, c.priority, c.category) == ("", 0, "")


# ---------------------------------------------------------------------------
# bg_notify
# ---------------------------------------------------------------------------
class TestBackgroundNotifier:
    def test_lifecycle_and_active_tasks(self):
        notifier = BackgroundNotifier()
        notifier.start_task("t1", "index")

        active = notifier.get_active_tasks()
        assert [a["id"] for a in active] == ["t1"]

        notifier.complete_task("t1", {"rows": 3})
        assert notifier.get_active_tasks() == []
        assert notifier.get_task("t1")["status"] == "completed"
        assert notifier.get_task("t1")["result"] == {"rows": 3}

    def test_unknown_task_is_ignored(self):
        notifier = BackgroundNotifier()
        notifier.complete_task("nope")
        notifier.fail_task("nope", "boom")
        assert notifier.get_task("nope") is None

    def test_fail_task_records_error(self):
        notifier = BackgroundNotifier()
        notifier.start_task("t1", "job")
        notifier.fail_task("t1", "boom")
        task = notifier.get_task("t1")
        assert task["status"] == "failed"
        assert task["error"] == "boom"

    def test_notification_is_sent_for_sync_callback(self):
        seen: list[tuple] = []
        notifier = BackgroundNotifier()
        notifier.set_notify_function(lambda platform, chat, msg: seen.append((platform, chat, msg)))
        notifier.start_task("t1", "job", notify_chat_id="42", notify_platform="tg")
        notifier.complete_task("t1")

        assert seen and seen[0][0] == "tg"
        assert seen[0][1] == "42"
        assert "completed" in seen[0][2]

    def test_notification_skipped_without_chat_id(self):
        seen: list[tuple] = []
        notifier = BackgroundNotifier()
        notifier.set_notify_function(lambda *a: seen.append(a))
        notifier.start_task("t1", "job")
        notifier.complete_task("t1")
        assert seen == []

    def test_notification_failure_is_contained(self):
        def boom(*_a):
            raise RuntimeError("notify failed")

        notifier = BackgroundNotifier()
        notifier.set_notify_function(boom)
        notifier.start_task("t1", "job", notify_chat_id="1")
        notifier.complete_task("t1")  # must not raise
        assert notifier.get_task("t1")["status"] == "completed"

    async def test_async_notification_is_scheduled_and_runs(self):
        calls: list[str] = []

        async def notify(platform, chat, msg):
            calls.append(msg)

        notifier = BackgroundNotifier()
        notifier.set_notify_function(notify)
        notifier.start_task("t1", "job", notify_chat_id="7", notify_platform="tg")
        notifier.complete_task("t1")
        # let the task created by asyncio.create_task actually run
        await asyncio.sleep(0)

        assert calls and "completed" in calls[0]

    def test_cleanup_old_removes_finished_tasks(self):
        notifier = BackgroundNotifier()
        notifier.start_task("t1", "job")
        notifier.complete_task("t1")
        notifier._tasks["t1"].end_time -= 10_000
        assert notifier.cleanup_old(max_age_seconds=3600) == 1
        assert notifier.get_task("t1") is None

    def test_cleanup_keeps_running_tasks(self):
        notifier = BackgroundNotifier()
        notifier.start_task("t1", "job")
        notifier._tasks["t1"].start_time -= 10_000
        assert notifier.cleanup_old() == 0

    def test_background_task_defaults(self):
        t = BackgroundTask(task_id="1", name="n")
        assert t.status == "pending" and t.error == ""


# ---------------------------------------------------------------------------
# browser
# ---------------------------------------------------------------------------
class TestBrowserTool:
    async def test_start_returns_false_when_playwright_missing(self):
        tool = BrowserTool()
        # playwright is not a dependency of bahram-agent, so start() must
        # degrade gracefully instead of raising ImportError.
        started = await tool.start()
        assert started is False
        assert tool.is_running() is False

    async def test_stop_without_start_does_not_raise(self):
        tool = BrowserTool()
        await tool.stop()  # regression: previously raised AttributeError

    @pytest.mark.parametrize(
        "method,args",
        [
            ("navigate", ("https://example.com",)),
            ("click", ("#btn",)),
            ("type_text", ("#input", "hello")),
            ("get_content", ()),
            ("screenshot", ()),
            ("evaluate", ("1 + 1",)),
        ],
    )
    async def test_operations_fail_closed_before_start(self, method, args):
        tool = BrowserTool()
        result = await getattr(tool, method)(*args)
        assert result in (
            False,
            None,
            "",
            {"error": "Browser not started"},
        ), f"{method} did not fail closed"

    def test_browser_state_defaults(self):
        s = BrowserState()
        assert (s.url, s.title, s.content, s.screenshot) == ("", "", "", b"")


# ---------------------------------------------------------------------------
# clarify
# ---------------------------------------------------------------------------
class TestClarifyTool:
    async def test_request_then_answer(self):
        tool = ClarifyTool()
        req = await tool.request_clarification(
            "Which DB?", context="setup", options=["sqlite", "pg"]
        )
        assert req["clarification_id"].startswith("clarify_")
        assert tool.has_pending() is True
        assert tool.get_pending_count() == 1
        assert tool.get_clarification(req["clarification_id"])["question"] == "Which DB?"

        assert tool.answer_clarification(req["clarification_id"], "sqlite") is True
        assert tool.has_pending() is False
        history = tool.get_history()
        assert history[0]["answer"] == "sqlite"
        assert history[0]["question"] == "Which DB?"

    async def test_answer_unknown_id_returns_false(self):
        tool = ClarifyTool()
        assert tool.answer_clarification("nope", "x") is False

    async def test_clear_pending(self):
        tool = ClarifyTool()
        await tool.request_clarification("q1")
        await tool.request_clarification("q2")
        assert tool.clear_pending() == 2
        assert tool.get_pending_count() == 0

    async def test_history_is_a_copy(self):
        tool = ClarifyTool()
        req = await tool.request_clarification("q")
        tool.answer_clarification(req["clarification_id"], "a")
        history = tool.get_history()
        history.clear()
        assert tool.get_history()


# ---------------------------------------------------------------------------
# code_review
# ---------------------------------------------------------------------------
class TestCodeReviewTool:
    async def test_review_code_flags_known_issues(self):
        tool = CodeReviewTool()
        issues = await tool.review_code("eval('1')\nprint('x')\n# TODO: fix")
        messages = {i.message for i in issues}
        assert "eval() usage - potential security risk" in messages
        assert "Consider using logging instead of print" in messages
        assert "TODO comment found" in messages
        assert all(i.file == "<code>" for i in issues)

    async def test_review_file_reads_from_disk(self, tmp_path: Path):
        src = tmp_path / "mod.py"
        src.write_text("try:\n    pass\nexcept:\n    pass\n")
        tool = CodeReviewTool()
        issues = await tool.review_file(str(src))
        assert issues and issues[0].file == str(src)
        assert issues[0].line == 3
        assert issues[0].category == "error"

    async def test_review_missing_file_returns_empty(self):
        tool = CodeReviewTool()
        assert await tool.review_file("/nonexistent/nope.py") == []

    async def test_clean_code_has_no_issues(self):
        tool = CodeReviewTool()
        assert await tool.review_code("value = 1\n") == []

    def test_summary_counts_by_severity(self):
        tool = CodeReviewTool()
        issues = [
            CodeIssue(file="f", line=1, severity="error", category="security", message="m"),
            CodeIssue(file="f", line=2, severity="info", category="style", message="m"),
        ]
        assert tool.get_summary(issues) == {"error": 1, "warning": 0, "info": 1}

    def test_format_report_empty_and_populated(self):
        tool = CodeReviewTool()
        assert tool.format_report([]) == "No issues found!"
        report = tool.format_report(
            [
                CodeIssue(
                    file="f.py",
                    line=1,
                    severity="error",
                    category="security",
                    message="eval() usage - potential security risk",
                    suggestion="Review for security implications",
                )
            ]
        )
        assert "Code Review Report" in report
        assert "f.py:1" in report
        assert "Review for security implications" in report

    def test_suggestion_lookup_falls_back_to_empty(self):
        tool = CodeReviewTool()
        assert tool._get_suggestion("unknown-category", "x") == ""


# ---------------------------------------------------------------------------
# code_search
# ---------------------------------------------------------------------------
class TestCodeSearchEngine:
    async def test_index_and_search(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("def alpha():\n    return 1\n")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.py").write_text("class Beta:\n    pass\n")

        engine = CodeSearchEngine()
        assert await engine.index_directory(str(tmp_path)) == 2

        results = await engine.search("alpha")
        assert results and results[0].file.endswith("a.py")
        assert results[0].line == 1
        assert "return 1" in results[0].context

    async def test_definition_match_scores_higher_than_plain_mention(self, tmp_path: Path):
        (tmp_path / "m.py").write_text("def target():\n    pass\nx = target()\n")
        engine = CodeSearchEngine()
        await engine.index_directory(str(tmp_path))
        results = await engine.search("target")
        assert results[0].line == 1  # the definition outranks the call site

    async def test_search_with_file_pattern_filters(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("needle = 1\n")
        (tmp_path / "b.py").write_text("needle = 2\n")
        engine = CodeSearchEngine()
        await engine.index_directory(str(tmp_path))
        results = await engine.search("needle", file_pattern=r"a\.py$")
        assert len(results) == 1 and results[0].file.endswith("a.py")

    async def test_search_respects_max_results(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("\n".join("hit = 1" for _ in range(20)))
        engine = CodeSearchEngine()
        await engine.index_directory(str(tmp_path))
        assert len(await engine.search("hit", max_results=3)) == 3

    async def test_find_definitions_and_references(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("def widget():\n    pass\nwidget()\n")
        engine = CodeSearchEngine()
        await engine.index_directory(str(tmp_path))

        defs = await engine.find_definitions("widget")
        assert len(defs) == 1 and "def widget" in defs[0].content

        refs = await engine.find_references("widget")
        assert len(refs) == 2

    def test_format_results_empty_and_populated(self):
        engine = CodeSearchEngine()
        assert engine.format_results([]) == "No results found!"
        out = engine.format_results([SearchResult(file="a.py", line=1, content="x", score=1.0)])
        assert "a.py:1" in out and "score: 1.00" in out

    async def test_index_directory_skips_unreadable_files(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("x = 1\n")
        engine = CodeSearchEngine()
        # A directory named *.py cannot be read as text; indexing must survive.
        (tmp_path / "broken.py").mkdir()
        assert await engine.index_directory(str(tmp_path)) == 1
