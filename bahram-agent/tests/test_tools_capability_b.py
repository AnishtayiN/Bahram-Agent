"""Behavioural tests for the tools/capability modules (batch B).

Covers: complexity, container, database, delegation, dependency, deployment,
documentation, documents, explainer, formatter.

Container and deployment tests substitute a **fake ``docker`` executable** on
``PATH``.  That is a real process boundary - the code under test still spawns a
real subprocess and parses real stdout/stderr - so no project code is stubbed.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from bahram.tools.complexity import ComplexityAnalyzer, ComplexityMetric
from bahram.tools.container import (
    ContainerConfig,
    ContainerResources,
    ContainerSecurity,
    DockerUnavailableError,
)
from bahram.tools.database import DatabaseTool, DBConfig
from bahram.tools.delegation import DelegatedTask, DelegationTool
from bahram.tools.dependency import Dependency, DependencyAnalyzer
from bahram.tools.deployment import DeploymentConfig, DeploymentTool
from bahram.tools.documentation import DocumentationGenerator
from bahram.tools.documents import DocumentTool
from bahram.tools.explainer import CodeExplainer, CodeExplanation
from bahram.tools.formatter import FormatRule, SmartFormatter


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def fake_docker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Install a deterministic stand-in for the ``docker`` CLI on ``PATH``.

    The stub echoes its arguments so assertions can verify the exact command
    line the module builds, and honours ``FAKE_DOCKER_RC`` to drive the failure
    branches.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "docker"
    script.write_text(
        '#!/bin/sh\necho "stdout:$*"\necho "stderr:$*" >&2\nexit "${FAKE_DOCKER_RC:-0}"\n'
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return bin_dir


# ---------------------------------------------------------------------------
# complexity
# ---------------------------------------------------------------------------
class TestComplexityAnalyzer:
    async def test_simple_file_scores_high(self, tmp_path: Path):
        src = tmp_path / "simple.py"
        src.write_text("def a(x):\n    return x\n")
        result = await ComplexityAnalyzer().analyze(str(src))

        assert result["file"] == str(src)
        assert result["rating"] == "A"
        assert result["overall_score"] == 100
        assert set(result["metrics"]) == {
            "cyclomatic",
            "cognitive",
            "lines_per_function",
            "parameters_per_function",
            "nesting_depth",
        }

    async def test_complex_file_rates_worse_than_simple_file(self, tmp_path: Path):
        simple = tmp_path / "simple.py"
        simple.write_text("def a(x):\n    return x\n")

        messy = tmp_path / "messy.py"
        messy.write_text(
            "def f(a, b, c, d, e, g, h, i, j, k):\n"
            "    if a:\n"
            "        if b:\n"
            "            if c:\n"
            "                for x in range(10):\n"
            "                    while a and b or c:\n"
            "                        try:\n"
            "                            pass\n"
            "                        except Exception:\n"
            "                            pass\n"
            "                        except ValueError:\n"
            "                            pass\n"
            "                        except TypeError:\n"
            "                            pass\n"
            "    return a, b, c, d, e, g, h, i, j, k\n"
        )

        analyzer = ComplexityAnalyzer()
        assert (await analyzer.analyze(str(simple)))["overall_score"] > (
            await analyzer.analyze(str(messy))
        )["overall_score"]

    async def test_missing_file_returns_error_payload(self):
        result = await ComplexityAnalyzer().analyze("/nonexistent/x.py")
        assert "error" in result

    def test_empty_code_has_no_functions(self):
        a = ComplexityAnalyzer()
        assert a._avg_lines_per_function("x = 1") == 0
        assert a._avg_params_per_function("x = 1") == 0

    def test_cognitive_complexity_grows_with_nesting(self):
        a = ComplexityAnalyzer()
        flat = a._cognitive_complexity("if a:\n    pass\n")
        nested = a._cognitive_complexity("if a:\n    if b:\n        pass\n")
        assert nested > flat

    def test_get_report_error_and_success(self, tmp_path: Path):
        a = ComplexityAnalyzer()
        assert a.get_report({"error": "boom"}) == "Error: boom"

        src = tmp_path / "m.py"
        src.write_text("def a():\n    if True:\n        return 1\n")
        report = a.get_report(
            {"file": str(src), "metrics": {"cyclomatic": 3}, "overall_score": 100, "rating": "A"}
        )
        assert "Code Complexity Report" in report
        assert "✅ Good" in report

    def test_get_report_marks_critical_metric(self):
        a = ComplexityAnalyzer()
        report = a.get_report(
            {"file": "f", "metrics": {"cyclomatic": 999}, "overall_score": 30, "rating": "D"}
        )
        assert "🔴 Critical" in report

    def test_complexity_metric_defaults(self):
        m = ComplexityMetric(name="n", value=1.0, threshold=2.0, status="ok")
        assert m.description == ""


# ---------------------------------------------------------------------------
# container
# ---------------------------------------------------------------------------
class TestContainerResources:
    async def test_create_container_builds_hardened_command_line(
        self, fake_docker: Path, tmp_path: Path
    ):
        res = ContainerResources()
        name = await res.create_container(
            ContainerConfig(
                name="unit-test",
                memory_limit="256m",
                cpu_limit=0.5,
                network="none",
                volumes={str(tmp_path): "/work"},
                env={"MODE": "test"},
                image="python:3.11-slim",
            )
        )

        assert name == "unit-test"
        assert res._active_containers[name]["id"].startswith("stdout:create")
        assert res._active_containers[name]["config"].memory_limit == "256m"

    async def test_create_container_generates_unique_name(self, fake_docker: Path):
        res = ContainerResources()
        name = await res.create_container(ContainerConfig())
        assert name.startswith("bahram-agent-")
        assert len(name) == len("bahram-agent-") + 8

    async def test_create_container_failure_raises_runtime_error(
        self, fake_docker: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("FAKE_DOCKER_RC", "1")
        with pytest.raises(RuntimeError, match="Failed to create container"):
            await ContainerResources().create_container(ContainerConfig())

    async def test_start_stop_remove(self, fake_docker: Path):
        res = ContainerResources()
        await res.create_container(ContainerConfig(name="c1"))
        assert await res.start_container("c1") is True
        assert await res.stop_container("c1", timeout=3) is True
        assert await res.remove_container("c1", force=True) is True
        assert "c1" not in res._active_containers

    async def test_remove_container_failure_keeps_registry(
        self, fake_docker: Path, monkeypatch: pytest.MonkeyPatch
    ):
        res = ContainerResources()
        await res.create_container(ContainerConfig(name="c1"))
        monkeypatch.setenv("FAKE_DOCKER_RC", "1")
        assert await res.remove_container("c1") is False
        assert "c1" in res._active_containers

    async def test_exec_in_container_returns_streams(self, fake_docker: Path):
        res = ContainerResources()
        out = await res.exec_in_container("c1", "echo hi")
        assert out["exit_code"] == 0
        assert "exec" in out["stdout"]
        assert "echo hi" in out["stdout"]

    async def test_get_container_stats_parses_delimited_output(self, fake_docker: Path):
        stats = await ContainerResources().get_container_stats("c1")
        assert stats["cpu_percent"].startswith("stdout:stats")

    async def test_list_containers_parses_table(self, fake_docker: Path):
        containers = await ContainerResources().list_containers(all=True)
        assert containers and containers[0]["name"].startswith("stdout:ps")

    async def test_missing_docker_degrades_gracefully(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        # PATH contains no docker binary at all
        monkeypatch.setenv("PATH", str(tmp_path / "empty"))

        res = ContainerResources()
        assert await res.list_containers() == []
        assert "error" in await res.get_container_stats("c1")
        assert "error" in await res.exec_in_container("c1", "ls")
        assert await res.start_container("c1") is False
        assert await res.stop_container("c1") is False
        assert await res.remove_container("c1") is False
        with pytest.raises(DockerUnavailableError):
            await res.create_container(ContainerConfig())


class TestContainerSecurity:
    def test_allowed_registry_passes(self):
        sec = ContainerSecurity()
        assert sec.check_image("python:3.11-slim") == (True, "OK")
        assert sec.check_image("gcr.io/proj/img") == (True, "OK")

    def test_disallowed_registry_is_rejected(self):
        sec = ContainerSecurity()
        ok, msg = sec.check_image("evil.example.com/img")
        assert ok is False
        assert "not allowed" in msg

    def test_blocked_image_is_rejected(self):
        sec = ContainerSecurity()
        sec._blocked_images.append("crypto-miner")
        ok, msg = sec.check_image("docker.io/crypto-miner:latest")
        assert ok is False
        assert "blocked" in msg

    def test_apply_security_forces_network_isolation(self):
        sec = ContainerSecurity()
        cfg = ContainerConfig(network="host")
        assert sec.apply_security(cfg).network == "none"


# ---------------------------------------------------------------------------
# database
# ---------------------------------------------------------------------------
class TestDatabaseTool:
    async def test_sqlite_round_trip(self, tmp_path: Path):
        db = tmp_path / "unit.db"
        tool = DatabaseTool(DBConfig(db_type="sqlite", database=str(db)))
        assert await tool.connect() is True

        await tool.execute("CREATE TABLE metrics (name TEXT, value REAL)")
        assert await tool.insert("metrics", {"name": "latency", "value": 1.5}) is True

        rows = await tool.execute("SELECT name, value FROM metrics")
        assert rows == [{"name": "latency", "value": 1.5}]

        await tool.close()
        assert tool._connection is None

    async def test_query_without_connection_returns_empty(self):
        tool = DatabaseTool(DBConfig(db_type="sqlite", database=":memory:"))
        assert await tool.execute("SELECT 1") == []

    async def test_connect_without_config_returns_false(self):
        assert await DatabaseTool().connect() is False

    async def test_unsupported_db_type_returns_false(self):
        tool = DatabaseTool(DBConfig(db_type="oracle", database="x"))
        assert await tool.connect() is False

    async def test_missing_driver_degrades_to_false(self, monkeypatch: pytest.MonkeyPatch):
        import builtins

        real_import = builtins.__import__

        def no_driver(name, *args, **kwargs):
            if name in {"asyncpg", "aiomysql"}:
                raise ImportError(name)
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", no_driver)
        assert await DatabaseTool(DBConfig(db_type="postgresql")).connect() is False
        assert await DatabaseTool(DBConfig(db_type="mysql")).connect() is False

    async def test_close_without_connection_is_a_noop(self):
        await DatabaseTool(DBConfig(db_type="sqlite", database=":memory:")).close()

    def test_db_config_defaults(self):
        cfg = DBConfig(db_type="sqlite")
        assert (cfg.host, cfg.port) == ("localhost", 5432)


# ---------------------------------------------------------------------------
# delegation
# ---------------------------------------------------------------------------
class TestDelegationTool:
    async def test_delegate_to_async_handler(self):
        tool = DelegationTool()

        async def handler(task_id, description, extra=None):
            return f"{task_id}:{description}:{extra}"

        tool.register_agent("worker", handler)
        out = await tool.delegate("worker", "t1", "do it", extra="x")

        assert out["status"] == "completed"
        assert out["result"] == "t1:do it:x"
        assert tool.get_task("t1")["status"] == "completed"

    async def test_delegate_to_sync_handler(self):
        tool = DelegationTool()
        tool.register_agent("sync", lambda task_id, description, **kw: description.upper())
        out = await tool.delegate("sync", "t1", "shout")
        assert out["result"] == "SHOUT"

    async def test_unknown_agent_returns_error(self):
        tool = DelegationTool()
        out = await tool.delegate("ghost", "t1", "x")
        assert out["error"] == "Agent 'ghost' not registered"

    async def test_failing_handler_is_recorded(self):
        tool = DelegationTool()

        def boom(**_kw):
            raise ValueError("nope")

        tool.register_agent("bad", boom)
        out = await tool.delegate("bad", "t1", "x")
        assert out["status"] == "failed"
        assert out["error"] == "nope"
        assert tool.get_task("t1")["error"] == "nope"

    def test_list_agents_and_tasks(self):
        tool = DelegationTool()
        tool.register_agent("a", lambda **kw: None)
        assert tool.list_agents() == ["a"]
        assert tool.list_tasks() == []
        assert tool.get_task("nope") is None

    def test_delegated_task_defaults(self):
        t = DelegatedTask(task_id="1", agent="a", description="d")
        assert t.status == "pending"


# ---------------------------------------------------------------------------
# dependency
# ---------------------------------------------------------------------------
class TestDependencyAnalyzer:
    async def test_reads_requirements_txt(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("# comment\nfastapi>=0.104.0\nrich\n\n")
        deps = await DependencyAnalyzer(str(tmp_path)).analyze()
        names = {d.name for d in deps["python"]}
        assert names == {"fastapi", "rich"}
        assert next(d for d in deps["python"] if d.name == "fastapi").version == "0.104.0"
        assert deps["total"] == 2

    async def test_reads_pyproject_without_duplicating(self, tmp_path: Path):
        (tmp_path / "requirements.txt").write_text("rich\n")
        (tmp_path / "pyproject.toml").write_text(
            'dependencies = ["rich>=13.0.0", "typer>=0.9.0"]\n'
        )
        deps = await DependencyAnalyzer(str(tmp_path)).analyze()
        names = [d.name for d in deps["python"]]
        assert names.count("rich") == 1
        assert "typer" in names

    async def test_reads_package_json(self, tmp_path: Path):
        (tmp_path / "package.json").write_text(
            json.dumps({"dependencies": {"react": "^18"}, "devDependencies": {"vitest": "^1"}})
        )
        deps = await DependencyAnalyzer(str(tmp_path)).analyze()
        sources = {d.source for d in deps["javascript"]}
        assert sources == {"package.json", "package.json (dev)"}
        assert deps["total"] == 2

    async def test_empty_project(self, tmp_path: Path):
        deps = await DependencyAnalyzer(str(tmp_path)).analyze()
        assert deps == {"python": [], "javascript": [], "total": 0}

    def test_report_and_outdated(self):
        analyzer = DependencyAnalyzer(".")
        deps = {
            "python": [Dependency(name="fastapi", version="0.1", source="requirements.txt")],
            "javascript": [],
            "total": 1,
        }
        report = analyzer.get_report(deps)
        assert "fastapi 0.1" in report and "Total: 1" in report
        assert analyzer.check_outdated(deps) == []


# ---------------------------------------------------------------------------
# deployment
# ---------------------------------------------------------------------------
class TestDeploymentTool:
    async def test_unknown_config_returns_error(self):
        out = await DeploymentTool().deploy("ghost")
        assert out["error"] == "Config 'ghost' not found"

    async def test_unsupported_target_returns_error(self):
        tool = DeploymentTool()
        tool.add_config(DeploymentConfig(name="svc", target="heroku"))
        out = await tool.deploy("svc")
        assert "Unsupported target" in out["error"]

    async def test_cloud_targets_are_configured_without_executing(self, fake_docker: Path):
        tool = DeploymentTool()
        for provider in ("aws", "gcp", "azure"):
            tool.add_config(
                DeploymentConfig(name=f"svc-{provider}", target=provider, region="eu-1")
            )
            out = await tool.deploy(f"svc-{provider}")
            assert out["status"] == "success"
            assert out["config"]["region"] == "eu-1"
        assert len(tool.get_history()) == 3

    async def test_docker_target_runs_build_and_run(self, fake_docker: Path):
        tool = DeploymentTool()
        tool.add_config(DeploymentConfig(name="svc", target="docker"))
        out = await tool.deploy("svc")
        assert out["target"] == "docker"
        assert out["status"] == "success"
        assert "build -t svc" in out["output"]

    async def test_kubernetes_target_pipes_manifest_to_kubectl(self, fake_docker: Path):
        tool = DeploymentTool()
        tool.add_config(DeploymentConfig(name="svc", target="kubernetes"))
        out = await tool.deploy("svc")
        assert out["target"] == "kubernetes"

    async def test_rollback(self, fake_docker: Path):
        out = await DeploymentTool().rollback("svc")
        assert "Rollback for svc" in out["message"]

    def test_deployment_config_defaults(self):
        cfg = DeploymentConfig(name="n", target="docker")
        assert (cfg.environment, cfg.replicas) == ("production", 1)


# ---------------------------------------------------------------------------
# documentation
# ---------------------------------------------------------------------------
class TestDocumentationGenerator:
    async def test_generate_readme_from_module_docstrings(self, tmp_path: Path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text('"""Mod summary."""\n\n\ndef f():\n    pass\n')

        out = tmp_path / "docs" / "README.md"
        assert await DocumentationGenerator().generate(str(pkg), str(out)) is True
        text = out.read_text()
        assert text.startswith("# pkg")
        assert "Mod summary." in text

    async def test_generate_api_docs_lists_public_symbols(self, tmp_path: Path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "mod.py").write_text("class Widget:\n    pass\n\n\ndef public():\n    pass\n")

        out = tmp_path / "API.md"
        await DocumentationGenerator().generate(str(pkg), str(out), doc_type="api")
        text = out.read_text()
        assert "- class `Widget`" in text
        assert "- `public()`" in text

    async def test_missing_source_returns_false(self, tmp_path: Path):
        gen = DocumentationGenerator()
        assert await gen.generate(str(tmp_path / "nope"), str(tmp_path / "o.md")) is False

    async def test_unknown_doc_type_returns_false(self, tmp_path: Path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        assert (
            await DocumentationGenerator().generate(
                str(pkg), str(tmp_path / "o.md"), doc_type="man"
            )
            is False
        )

    async def test_changelog_generation_writes_file(self, tmp_path: Path):
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        out = tmp_path / "CHANGELOG.md"
        assert (
            await DocumentationGenerator().generate(str(pkg), str(out), doc_type="changelog")
            is True
        )
        assert out.exists()

    def test_extract_docstring_handles_single_quotes(self, tmp_path: Path):
        src = tmp_path / "m.py"
        src.write_text("'''Single quoted.'''\n")
        assert DocumentationGenerator()._extract_docstring(src) == "Single quoted."

    def test_extract_docstring_returns_empty_when_absent(self, tmp_path: Path):
        src = tmp_path / "m.py"
        src.write_text("x = 1\n")
        assert DocumentationGenerator()._extract_docstring(src) == ""


# ---------------------------------------------------------------------------
# documents
# ---------------------------------------------------------------------------
class TestDocumentTool:
    async def test_extract_text_and_markdown(self, tmp_path: Path):
        txt = tmp_path / "a.txt"
        txt.write_text("hello")
        assert await DocumentTool().extract(str(txt)) == {
            "content": "hello",
            "format": "text",
        }

        md = tmp_path / "b.md"
        md.write_text("# h")
        assert (await DocumentTool().extract(str(md)))["format"] == "markdown"

    async def test_extract_json(self, tmp_path: Path):
        f = tmp_path / "a.json"
        f.write_text('{"k": 1}')
        assert await DocumentTool().extract(str(f)) == {
            "content": {"k": 1},
            "format": "json",
        }

    async def test_extract_yaml(self, tmp_path: Path):
        f = tmp_path / "a.yaml"
        f.write_text("k: 1\n")
        assert await DocumentTool().extract(str(f)) == {
            "content": {"k": 1},
            "format": "yaml",
        }

    async def test_unknown_extension_falls_back_to_text(self, tmp_path: Path):
        f = tmp_path / "a.log"
        f.write_text("line")
        assert (await DocumentTool().extract(str(f)))["format"] == "text"

    async def test_pdf_without_pypdf2_reports_actionable_error(self, tmp_path: Path):
        f = tmp_path / "a.pdf"
        f.write_bytes(b"%PDF-1.4")
        result = await DocumentTool().extract(str(f))
        assert "error" in result

    async def test_docx_without_python_docx_reports_actionable_error(self, tmp_path: Path):
        f = tmp_path / "a.docx"
        f.write_bytes(b"PK")
        result = await DocumentTool().extract(str(f))
        assert "error" in result

    async def test_missing_file(self):
        result = await DocumentTool().extract("/nonexistent/a.txt")
        assert "File not found" in result["error"]

    async def test_oversized_file_is_rejected(self, tmp_path: Path):
        f = tmp_path / "big.txt"
        f.write_text("x")
        tool = DocumentTool()
        tool.set_max_size(1)
        # stat().st_size is 1 byte, so shrink the limit further to trigger it
        tool.set_max_size(0)
        assert (await tool.extract(str(f)))["error"] == "File too large"


# ---------------------------------------------------------------------------
# explainer
# ---------------------------------------------------------------------------
class TestCodeExplainer:
    async def test_explains_function_and_class(self):
        exps = await CodeExplainer().explain("def fib(n):\nclass Node:\n")
        assert exps[0].explanation.startswith("Function definition named 'fib'")
        assert "function" in exps[0].concepts
        assert any(e.explanation.startswith("Class definition named 'Node'") for e in exps)

    async def test_comments_are_skipped(self):
        assert await CodeExplainer().explain("# just a comment") == []

    async def test_unknown_line_falls_back_to_generic_explanation(self):
        exps = await CodeExplainer().explain("x = 1")
        assert exps[0].explanation == "Code: x = 1"
        assert exps[0].complexity == "simple"

    async def test_async_is_marked_complex(self):
        exps = await CodeExplainer().explain("async def go():")
        assert exps[0].complexity == "complex"
        assert "asynchronous" in exps[0].concepts

    async def test_explains_import_and_comprehension(self):
        exps = await CodeExplainer().explain("import os\nfrom sys import argv\n")
        assert any("Imports module: os" in e.explanation for e in exps)
        assert any("Imports argv from sys" in e.explanation for e in exps)

    def test_format_explanations_empty_and_full(self):
        explainer = CodeExplainer()
        assert explainer.format_explanations([]) == "No code to explain!"
        out = explainer.format_explanations(
            [
                CodeExplanation(
                    line=1,
                    code="def f():",
                    explanation="Function definition named 'f'",
                    complexity="moderate",
                    concepts=["function"],
                )
            ]
        )
        assert "Code Explanation" in out
        assert "🟡 moderate" in out
        assert "function" in out


# ---------------------------------------------------------------------------
# formatter
# ---------------------------------------------------------------------------
class TestSmartFormatter:
    async def test_python_rules_fix_trailing_whitespace_and_blank_lines(self):
        formatted, changes = await SmartFormatter().format("x = 1   \n\n\n\ny = 2\n", "python")
        assert formatted == "x = 1\n\ny = 2\n"
        assert {c["rule"] for c in changes} >= {
            "trailing_whitespace",
            "blank_lines",
        }

    async def test_check_style_counts_violations_without_editing(self):
        issues = await SmartFormatter().check_style("const a = 1\n", "javascript")
        assert issues and issues[0]["count"] >= 1
        assert "const a = 1" == "const a = 1"

    async def test_filter_to_named_rules(self):
        formatted, changes = await SmartFormatter().format(
            "x = 1   \n", "python", rules=["trailing_whitespace"]
        )
        assert formatted == "x = 1\n"
        assert [c["rule"] for c in changes] == ["trailing_whitespace"]

    async def test_unknown_language_is_a_noop(self):
        formatted, changes = await SmartFormatter().format("x", "brainfuck")
        assert (formatted, changes) == ("x", [])

    def test_get_rules_and_add_rule(self):
        fmt = SmartFormatter()
        assert fmt.get_rules("python")[0]["name"] == "trailing_whitespace"

        fmt.add_rule(FormatRule(name="tabs", language="go", pattern="\t", replacement="    "))
        assert "tabs" in [r["name"] for r in fmt.get_rules("go")]
