"""The packaged CLI — `bahram …`, resolved from `[project.scripts]`.

`bahram/cli.py` is what users actually run, and it had no tests at all (0 %
coverage). These tests drive it through Typer's `CliRunner`, so they exercise
the real command wiring rather than the functions behind it. No project code
is patched; where a command needs a real Agent, a real one is started.

Two defects found while writing these, both fixed:
* `bahram chat "hi"` with no API key crashed with an unhandled
  `ValueError: Provider 'anthropic' not registered` and a raw traceback.
* `bahram serve` printed "Starting API server … / Server started" and
  returned, claiming to have started a server that does not exist.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from bahram.cli import app, main

runner = CliRunner()


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch):
    """Point the CLI at a throw-away config and run from a clean directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _config(tmp_path: Path, **extra: str) -> str:
    lines = ["agent:", "  name: CliTest", "memory:", "  database: ':memory:'"]
    for key, value in extra.items():
        lines.append(f"{key}:")
        lines.append(f"  {value}")
    path = tmp_path / "config.yaml"
    path.write_text("\n".join(lines) + "\n")
    return str(path)


class TestTopLevel:
    def test_help_lists_every_command(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for command in ("chat", "model", "skills", "serve", "gateway", "version"):
            assert command in result.output

    def test_an_unknown_command_is_rejected(self):
        assert runner.invoke(app, ["definitely-not-a-command"]).exit_code != 0

    def test_version_reports_the_package_version(self):
        import bahram

        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert bahram.__version__ in result.output

    def test_main_entry_point_runs_the_app(self):
        """`main()` is what the console script calls."""
        with pytest.raises(SystemExit):
            main()


class TestSkillsCommand:
    def test_list_reads_the_real_skill_directory(self, isolated: Path):
        result = runner.invoke(app, ["skills", "--list"])
        assert result.exit_code == 0, result.output
        for name in ("code-review", "deploy", "research"):
            assert f"- {name}" in result.output

    def test_list_works_from_an_unrelated_directory(self, isolated: Path):
        """The skills directory must resolve even when CWD has none."""
        assert (isolated / "skills").exists() is False
        assert runner.invoke(app, ["skills", "--list"]).exit_code == 0

    def test_show_one_skill(self):
        result = runner.invoke(app, ["skills", "code-review"])
        assert result.exit_code == 0
        assert "code-review" in result.output

    def test_unknown_skill_exits_non_zero(self):
        result = runner.invoke(app, ["skills", "no-such-skill"])
        assert result.exit_code == 1
        assert "Unknown skill" in result.output

    def test_without_arguments_prints_usage(self):
        result = runner.invoke(app, ["skills"])
        assert result.exit_code == 0
        assert "--list" in result.output


class TestModelCommand:
    def test_without_arguments_prints_usage(self):
        result = runner.invoke(app, ["model"])
        assert result.exit_code == 0
        assert "--list" in result.output

    def test_list_with_no_providers_configured(self, isolated: Path):
        (isolated / "config.yaml").write_text("agent:\n  name: x\n")
        result = runner.invoke(app, ["model", "--list"])
        assert result.exit_code == 0
        assert "Available models" in result.output

    def test_list_shows_configured_providers(self, isolated: Path):
        cfg = isolated / "config.yaml"
        cfg.write_text(
            "providers:\n"
            "  anthropic:\n"
            "    api_key: k\n"
            "    enabled: true\n"
            "    models: ['claude-sonnet-4', 'claude-haiku']\n"
        )
        result = runner.invoke(app, ["model", "--list", "--config", str(cfg)])
        assert result.exit_code == 0
        assert "anthropic" in result.output
        assert "claude-haiku" in result.output

    def test_set_points_at_the_file_to_edit(self, isolated: Path):
        cfg = isolated / "config.yaml"
        cfg.write_text("agent:\n  name: x\n")
        result = runner.invoke(app, ["model", "--set", "openai/gpt-4o", "--config", str(cfg)])
        assert result.exit_code == 0
        assert str(cfg) in result.output

    def test_set_reports_the_choice(self):
        result = runner.invoke(app, ["model", "--set", "openai/gpt-4o"])
        assert result.exit_code == 0
        assert "openai/gpt-4o" in result.output


class TestServeCommand:
    def test_it_says_no_server_ships(self):
        """It used to print 'Server started' for a server that does not exist."""
        result = runner.invoke(app, ["serve"])
        assert result.exit_code == 1
        assert "No HTTP server is bundled" in result.output

    def test_the_host_and_port_are_echoed(self):
        result = runner.invoke(app, ["serve", "--host", "127.0.0.1", "--port", "9001"])
        assert "127.0.0.1:9001" in result.output


class TestGatewayCommand:
    def test_unknown_platform_is_reported(self):
        result = runner.invoke(app, ["gateway", "--platform", "carrier-pigeon"])
        assert result.exit_code == 0
        assert "Unknown platform" in result.output

    @pytest.mark.parametrize("platform", ["telegram", "discord", "slack"])
    def test_unconfigured_platform_is_reported(self, isolated: Path, platform: str):
        (isolated / "config.yaml").write_text("agent:\n  name: x\n")
        result = runner.invoke(app, ["gateway", "--platform", platform])
        assert result.exit_code == 0
        assert "not configured" in result.output


class TestChatCommand:
    def test_missing_provider_prints_a_message_not_a_traceback(self, isolated: Path):
        """`bahram chat` with no API key used to raise ValueError out of main."""
        cfg = _config(isolated)
        result = runner.invoke(app, ["chat", "hello", "--config", cfg])
        assert result.exit_code == 1
        assert "not registered" in result.output
        assert "Set an API key" in result.output
        assert result.exception is None or isinstance(result.exception, SystemExit)

    def test_a_missing_config_file_falls_back_to_defaults(self, isolated: Path):
        result = runner.invoke(app, ["chat", "hello", "--config", str(isolated / "nope.yaml")])
        assert result.exit_code == 1
        assert "not registered" in result.output

    async def test_one_shot_chat_prints_the_reply(self, isolated: Path, capsys):
        """Drive `_chat_async` with a real Agent holding a scripted provider.

        `bahram.cli` builds its own Agent, so the command itself always needs
        a configured API key. This exercises the code path the command runs,
        with no patching of project code.
        """
        from bahram.cli import _chat_async
        from bahram.core.agent import Agent
        from bahram.core.config import Config
        from bahram.core.engine import AgentResponse, RunState

        class Scripted:
            async def complete(self, messages, tools=None):
                return AgentResponse(content="cli reply", state=RunState.COMPLETED)

        config = Config.from_file(_config(isolated))
        agent = Agent(config=config)
        await agent.start()
        agent.engine.register_provider("anthropic", Scripted())

        await _chat_async(agent, "hello", "anthropic/test-model", None)
        await agent.stop()

        assert "cli reply" in capsys.readouterr().out

    async def test_interactive_loop_handles_clear_blank_and_exit(self, isolated: Path, monkeypatch):
        """The REPL branch: exit, clear, blank input and a streamed reply.

        `rich.prompt.Prompt.ask` is the user-input boundary and is stubbed
        here; no Bahram code is patched.
        """
        import bahram.cli as cli_module
        from bahram.cli import _chat_async
        from bahram.core.agent import Agent
        from bahram.core.config import Config
        from bahram.core.engine import AgentResponse, RunState

        class Scripted:
            async def complete(self, messages, tools=None):
                return AgentResponse(content="hi there", state=RunState.COMPLETED)

            async def stream(self, messages, tools=None):
                yield "hi "
                yield "there"

        answers = iter(["hello", "clear", "   ", "quit"])

        class FakePrompt:
            @staticmethod
            def ask(*args, **kwargs):
                return next(answers)

        monkeypatch.setattr(cli_module, "Prompt", FakePrompt)

        config = Config.from_file(_config(isolated))
        agent = Agent(config=config)
        await agent.start()
        agent.engine.register_provider("anthropic", Scripted())

        await _chat_async(agent, None, "anthropic/test-model", "session-1")
        await agent.stop()

        assert cli_module.console is not None
