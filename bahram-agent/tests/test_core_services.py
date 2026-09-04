"""Core services that sit under the agent: config, context, compressor,
persistence and the secret store.

Each of these is used by ``Agent`` but was only exercised incidentally, so the
branches that matter - trimming, compression fallbacks, trajectory round trips,
secret round trips - were never really run.  These tests drive them directly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from bahram.core.compressor import CompressionResult, ContextCompressor
from bahram.core.config import Config
from bahram.core.context import Context, ContextWindow
from bahram.core.engine import Message, MessageRole, Trajectory, TrajectoryStep
from bahram.core.persistence import SessionStore
from bahram.core.secrets import SecretEntry, SecretsManager


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------
class TestConfig:
    def test_defaults_are_consistent(self):
        config = Config()
        assert config.agent.name
        assert config.agent.version
        assert config.memory.max_context_turns > 0
        assert config.logging.level
        assert config.server.host

    def test_round_trip_through_yaml(self, tmp_path: Path):
        path = tmp_path / "config.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "agent": {"name": "RoundTrip", "model": "fake/model-9"},
                    "memory": {"database": ":memory:"},
                }
            )
        )

        reloaded = Config.from_file(str(path))
        assert reloaded.agent.name == "RoundTrip"
        assert reloaded.agent.model == "fake/model-9"
        assert reloaded.memory.database == ":memory:"

    def test_from_file_reads_a_partial_file(self, tmp_path: Path):
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump({"agent": {"name": "Partial"}}))
        config = Config.from_file(str(path))
        assert config.agent.name == "Partial"
        # everything else keeps its default
        assert config.agent.model == Config().agent.model

    def test_from_file_with_unknown_keys_is_tolerated(self, tmp_path: Path, capsys):
        """A stray key must cost one setting, not abort start-up."""
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump({"agent": {"name": "X", "not_a_field": 1}}))
        assert Config.from_file(str(path)).agent.name == "X"
        assert "unknown key" in capsys.readouterr().out

    def test_from_file_rejects_a_non_mapping_section(self, tmp_path: Path):
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump({"agent": "not a mapping"}))
        with pytest.raises(TypeError):
            Config.from_file(str(path))

    def test_from_file_expands_environment_variables(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("BAHRAM_TEST_MODEL", "expanded/model")
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump({"agent": {"model": "${BAHRAM_TEST_MODEL}"}}))
        assert Config.from_file(str(path)).agent.model == "expanded/model"

    def test_from_file_expands_inside_lists(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("BAHRAM_TEST_ITEM", "item-from-env")
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump({"security": {"allowed_commands": ["${BAHRAM_TEST_ITEM}"]}}))
        assert Config.from_file(str(path)).security.allowed_commands == ["item-from-env"]

    def test_from_a_missing_file_returns_defaults(self, tmp_path: Path):
        assert Config().from_file(str(tmp_path / "nope.yaml")).agent.name == Config().agent.name

    def test_from_a_file_that_is_not_yaml(self, tmp_path: Path, capsys):
        path = tmp_path / "config.yaml"
        path.write_text("agent: [unclosed\n  - :::\n")
        config = Config.from_file(str(path))
        assert config.agent.name == Config().agent.name
        assert "Failed to load config" in capsys.readouterr().out

    def test_providers_and_platforms_are_parsed(self, tmp_path: Path):
        path = tmp_path / "config.yaml"
        path.write_text(
            yaml.safe_dump(
                {
                    "providers": {"anthropic": {"api_key": "k", "enabled": True}},
                    "platforms": {"telegram": {"enabled": False}},
                }
            )
        )
        config = Config.from_file(str(path))
        assert config.providers["anthropic"].api_key == "k"
        assert config.platforms["telegram"].enabled is False

    def test_get_provider_and_model_provider(self, tmp_path: Path):
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump({"providers": {"anthropic": {"api_key": "k"}}}))
        config = Config.from_file(str(path))

        assert config.get_provider("anthropic").api_key == "k"
        assert config.get_model_provider("anthropic/claude-x")[0] == "anthropic"
        assert config.get_model_provider("bare-model")[0] == "anthropic"
        with pytest.raises(ValueError):
            config.get_provider("openai")

    def test_security_requires_approval_defaults(self):
        assert "bash" in Config().security.require_approval


# ---------------------------------------------------------------------------
# context
# ---------------------------------------------------------------------------
class TestContextWindow:
    def _msg(self, role: MessageRole, content: str) -> Message:
        return Message(role=role, content=content)

    def test_system_prompt_lifecycle(self):
        window = ContextWindow()
        assert window.get_system_prompt() is None

        window.set_system_prompt("be brief")
        assert window.get_system_prompt() == "be brief"

        window.set_system_prompt("be terse")
        assert window.get_system_prompt() == "be terse"
        assert len(window.messages) == 1

    def test_add_messages_and_get_a_copy(self):
        window = ContextWindow()
        window.add_message(self._msg(MessageRole.USER, "hi"))
        window.add_messages([self._msg(MessageRole.ASSISTANT, "hello")])

        messages = window.get_messages()
        assert [m.content for m in messages] == ["hi", "hello"]
        messages.clear()  # the returned list is a copy
        assert len(window.get_messages()) == 2

    def test_trimming_summarises_the_old_half(self):
        window = ContextWindow(max_turns=4)
        for i in range(10):
            window.add_message(self._msg(MessageRole.USER, f"question {i}"))
            window.add_message(self._msg(MessageRole.ASSISTANT, f"answer {i}"))

        assert len(window.summaries) >= 1
        assert window.summaries[0].startswith("[Summary of conversation up to:")
        assert len(window.get_messages()) < 20

    def test_system_messages_survive_trimming(self):
        window = ContextWindow(max_turns=2)
        window.set_system_prompt("stay in character")
        for i in range(8):
            window.add_message(self._msg(MessageRole.USER, f"q{i}"))
            window.add_message(self._msg(MessageRole.ASSISTANT, f"a{i}"))

        assert window.get_system_prompt() == "stay in character"

    def test_summary_of_an_empty_batch(self):
        window = ContextWindow()
        assert window._summarize_messages([]) == "[Empty conversation summary]"

    def test_clear(self):
        window = ContextWindow()
        window.add_message(self._msg(MessageRole.USER, "hi"))
        window.clear()
        assert window.get_messages() == []
        assert window.summaries == []

    def test_to_dict_and_back(self):
        window = ContextWindow()
        window.set_system_prompt("sys")
        window.add_message(self._msg(MessageRole.USER, "hi"))

        restored = ContextWindow.from_dict(window.to_dict())
        assert restored.get_system_prompt() == "sys"
        assert [m.content for m in restored.get_messages()] == ["sys", "hi"]


class TestContextRegistry:
    def test_create_get_delete(self):
        ctx = Context(max_turns=5)
        assert ctx.get("nope") is None

        window = ctx.create("s1")
        assert ctx.get("s1") is window
        assert ctx.get_or_create("s1") is window
        assert ctx.list_sessions() == ["s1"]

        ctx.delete("s1")
        assert ctx.get("s1") is None
        ctx.delete("s1")  # deleting twice is a no-op

    def test_active_session(self):
        ctx = Context()
        assert ctx.get_active() is None

        window = ctx.get_or_create("s1")
        ctx.set_active("s1")
        assert ctx.get_active() is window

        ctx.set_active("missing")
        assert ctx.get_active() is None

    def test_clear_one_session(self):
        ctx = Context()
        window = ctx.get_or_create("s1")
        window.add_message(Message(role=MessageRole.USER, content="hi"))
        ctx.clear("s1")
        assert window.get_messages() == []
        ctx.clear("unknown")  # no-op

    def test_max_turns_is_propagated(self):
        assert Context(max_turns=3).get_or_create("s").max_turns == 3


# ---------------------------------------------------------------------------
# compressor
# ---------------------------------------------------------------------------
class TestContextCompressor:
    @pytest.fixture
    def compressor(self) -> ContextCompressor:
        return ContextCompressor()

    def _long(self, count: int = 60) -> list[dict]:
        return [
            {"role": "user" if i % 2 else "assistant", "content": f"message {i} " * 40}
            for i in range(count)
        ]

    async def test_short_context_is_returned_unchanged(self, compressor: ContextCompressor):
        messages = [{"role": "user", "content": "hi"}]
        result = await compressor.compress(messages, target_tokens=4000)
        assert isinstance(result, CompressionResult)
        assert result.ratio == 1.0
        assert json.loads(result.compressed) == messages

    async def test_disabled_compressor_passes_everything_through(
        self, compressor: ContextCompressor
    ):
        compressor.set_enabled(False)
        result = await compressor.compress(self._long(), target_tokens=10)
        assert result.original_tokens == 0
        assert result.ratio == 1.0

    async def test_empty_message_list(self, compressor: ContextCompressor):
        result = await compressor.compress([], target_tokens=10)
        assert json.loads(result.compressed) == []

    async def test_heuristic_compression_keeps_the_tail(self, compressor: ContextCompressor):
        messages = self._long()
        result = await compressor.compress(messages, target_tokens=400)
        assert result.compressed_tokens < result.original_tokens
        assert result.ratio < 1.0
        decoded = json.loads(result.compressed)
        assert decoded[-1]["content"].startswith("message 59")

    async def test_heuristic_compression_keeps_the_system_message(
        self, compressor: ContextCompressor
    ):
        messages = [{"role": "system", "content": "you are Bahram"}] + self._long()
        decoded = json.loads((await compressor.compress(messages, target_tokens=400)).compressed)
        assert decoded[0]["role"] == "system"
        assert decoded[0]["content"] == "you are Bahram"

    async def test_a_compression_notice_is_inserted(self, compressor: ContextCompressor):
        decoded = json.loads(
            (await compressor.compress(self._long(), target_tokens=400)).compressed
        )
        assert any("Context compressed:" in m.get("content", "") for m in decoded)

    async def test_model_compression_is_used_when_provided(self, compressor: ContextCompressor):
        seen: list[list[dict]] = []

        async def fake_model(messages: list[dict]) -> str:
            seen.append(messages)
            return "a very short summary"

        result = await compressor.compress(self._long(), model_fn=fake_model, target_tokens=400)
        assert result.compressed == "a very short summary"
        assert "Compress the following conversation" in seen[0][0]["content"]

    async def test_model_failure_falls_back_to_the_heuristic(self, compressor: ContextCompressor):
        async def broken_model(messages: list[dict]) -> str:
            raise RuntimeError("model offline")

        result = await compressor.compress(self._long(), model_fn=broken_model, target_tokens=400)
        assert result.ratio < 1.0
        assert json.loads(result.compressed)  # valid JSON from the heuristic path

    async def test_heuristic_on_an_empty_list(self, compressor: ContextCompressor):
        assert compressor._heuristic_compress([], 100) == "[]"

    def test_set_level_is_clamped(self, compressor: ContextCompressor):
        compressor.set_level(5)
        assert compressor._compression_level == 1
        compressor.set_level(-5)
        assert compressor._compression_level == 0


# ---------------------------------------------------------------------------
# persistence
# ---------------------------------------------------------------------------
class TestSessionStore:
    @pytest.fixture
    def store(self, tmp_path: Path) -> SessionStore:
        return SessionStore(str(tmp_path / "sessions.db"))

    def test_session_crud(self, store: SessionStore):
        created = store.create_session(
            "s1", user_id="u1", channel="cli", model="m", metadata={"k": "v"}
        )
        assert created["id"] == "s1"

        loaded = store.get_session("s1")
        assert loaded["user_id"] == "u1"
        assert json.loads(loaded["metadata"]) == {"k": "v"}

        store.update_session("s1", user_id="u2", channel="web", model="m2", metadata={"k": "w"})
        updated = store.get_session("s1")
        assert updated["user_id"] == "u2"
        assert updated["channel"] == "web"
        assert json.loads(updated["metadata"]) == {"k": "w"}

        assert store.list_sessions() and store.list_sessions()[0]["id"] == "s1"

    def test_get_missing_session_returns_none(self, store: SessionStore):
        assert store.get_session("nope") is None

    def test_update_with_unknown_fields_is_ignored(self, store: SessionStore):
        store.create_session("s1")
        store.update_session("s1", not_a_column="x")
        assert store.get_session("s1")["id"] == "s1"

    def test_messages_round_trip_in_order(self, store: SessionStore):
        store.create_session("s1")
        store.add_message("s1", Message(role=MessageRole.USER, content="first"))
        store.add_message("s1", Message(role=MessageRole.ASSISTANT, content="second"))

        messages = store.get_messages("s1")
        assert [m.content for m in messages] == ["first", "second"]
        assert messages[0].role is MessageRole.USER

    def test_message_metadata_is_persisted(self, store: SessionStore):
        store.create_session("s1")
        store.add_message("s1", Message(role=MessageRole.USER, content="x", metadata={"a": 1}))
        assert store.get_messages("s1")[0].metadata == {"a": 1}

    def test_get_messages_respects_the_limit(self, store: SessionStore):
        store.create_session("s1")
        for i in range(5):
            store.add_message("s1", Message(role=MessageRole.USER, content=str(i)))
        assert len(store.get_messages("s1", limit=2)) == 2

    def test_clear_messages(self, store: SessionStore):
        store.create_session("s1")
        store.add_message("s1", Message(role=MessageRole.USER, content="x"))
        store.clear_messages("s1")
        assert store.get_messages("s1") == []

    def test_delete_session_cascades(self, store: SessionStore):
        store.create_session("s1")
        store.add_message("s1", Message(role=MessageRole.USER, content="x"))
        trajectory = Trajectory(run_id="r1", session_id="s1", goal="g")
        store.save_trajectory(trajectory, "s1")
        store.log_tool_call("r1", "bash", {"command": "ls"}, "ok")

        store.delete_session("s1")
        assert store.get_session("s1") is None
        assert store.get_messages("s1") == []
        assert store.get_trajectory("r1") is None

    def test_trajectory_round_trip(self, store: SessionStore):
        store.create_session("s1")
        trajectory = Trajectory(run_id="r1", session_id="s1", goal="do it", status="completed")
        trajectory.steps.append(
            TrajectoryStep(
                step_id="step_0",
                timestamp=1.0,
                iteration=0,
                provider="fake",
                model="m",
                tool_calls=[{"name": "bash"}],
                tool_results=[{"ok": True}],
                content_length=10,
                duration_ms=5.0,
                state="completed",
            )
        )
        assert store.save_trajectory(trajectory, "s1") == "r1"

        loaded = store.get_trajectory("r1")
        assert loaded["run"]["goal"] == "do it"
        assert loaded["run"]["status"] == "completed"
        assert len(loaded["steps"]) == 1
        assert json.loads(loaded["steps"][0]["tool_calls"]) == [{"name": "bash"}]

    def test_get_missing_trajectory_returns_none(self, store: SessionStore):
        assert store.get_trajectory("nope") is None

    def test_tool_calls_and_events(self, store: SessionStore):
        call_id = store.log_tool_call("r1", "bash", {"command": "ls"}, "ok", result="out")
        assert call_id

        store.log_event("tool", "bash", {"x": 1})
        store.log_event("run", "engine", {"y": 2})

        assert len(store.get_events()) == 2
        assert [e["data"] for e in store.get_events(event_type="tool")] == ['{"x": 1}']

    def test_get_recent_runs(self, store: SessionStore):
        store.create_session("s1")
        store.save_trajectory(Trajectory(run_id="r1", session_id="s1", goal="a"), "s1")
        store.save_trajectory(Trajectory(run_id="r2", session_id="s1", goal="b"), "s1")
        assert len(store.get_recent_runs(limit=1)) == 1

    def test_in_memory_store_creates_no_file(self, tmp_path: Path):
        store = SessionStore(":memory:")
        store.create_session("s1")
        store.add_message("s1", Message(role=MessageRole.USER, content="x"))
        assert store.get_messages("s1")
        assert list(tmp_path.iterdir()) == []

    def test_on_disk_store_is_reopened(self, tmp_path: Path):
        path = str(tmp_path / "sessions.db")
        first = SessionStore(path)
        first.create_session("s1")
        first.add_message("s1", Message(role=MessageRole.USER, content="persisted"))

        second = SessionStore(path)
        assert [m.content for m in second.get_messages("s1")] == ["persisted"]


# ---------------------------------------------------------------------------
# secrets
# ---------------------------------------------------------------------------
class TestSecretsManager:
    @pytest.fixture
    def manager(self, tmp_path: Path) -> SecretsManager:
        return SecretsManager(str(tmp_path / "secrets"))

    def test_set_get_delete(self, manager: SecretsManager):
        manager.set_secret("OPENAI_API_KEY", "sk-1234567890", description="openai", category="llm")
        assert manager.get_secret("OPENAI_API_KEY") == "sk-1234567890"
        assert manager.get_secret_info("OPENAI_API_KEY") == {
            "name": "OPENAI_API_KEY",
            "description": "openai",
            "category": "llm",
            "created_at": manager.get_secret_info("OPENAI_API_KEY")["created_at"],
        }

        assert manager.delete_secret("OPENAI_API_KEY") is True
        assert manager.delete_secret("OPENAI_API_KEY") is False
        assert manager.get_secret("OPENAI_API_KEY") is None

    def test_get_secret_info_for_an_unknown_name(self, manager: SecretsManager):
        assert manager.get_secret_info("nope") is None

    def test_list_secrets_and_filter_by_category(self, manager: SecretsManager):
        manager.set_secret("A", "value-a", category="llm")
        manager.set_secret("B", "value-b", category="db")

        assert {s["name"] for s in manager.list_secrets()} == {"A", "B"}
        assert [s["name"] for s in manager.list_secrets(category="llm")] == ["A"]

    def test_persists_across_instances(self, tmp_path: Path):
        data_dir = str(tmp_path / "secrets")
        SecretsManager(data_dir).set_secret("TOKEN", "super-secret-value")

        reloaded = SecretsManager(data_dir)
        assert reloaded.get_secret("TOKEN") == "super-secret-value"

    def test_the_store_is_not_plaintext(self, tmp_path: Path):
        """The secret must not be recoverable by reading the file."""
        data_dir = tmp_path / "secrets"
        manager = SecretsManager(str(data_dir))
        manager.set_secret("TOKEN", "super-secret-value")

        on_disk = (data_dir / "secrets.enc").read_text()
        assert "super-secret-value" not in on_disk

    def test_the_key_file_is_not_world_readable(self, tmp_path: Path):
        import os
        import stat

        data_dir = tmp_path / "secrets"
        SecretsManager(str(data_dir))
        mode = os.stat(data_dir / ".key").st_mode
        assert not mode & (stat.S_IRWXG | stat.S_IRWXO)

    def test_corrupt_store_is_ignored(self, tmp_path: Path):
        data_dir = tmp_path / "secrets"
        data_dir.mkdir()
        (data_dir / "secrets.enc").write_text("not base64 at all!!!")
        assert SecretsManager(str(data_dir)).list_secrets() == []

    def test_import_from_env(self, manager: SecretsManager, monkeypatch):
        monkeypatch.setenv("SECRET_ONE", "value-one")
        monkeypatch.setenv("API_TWO", "value-two")
        monkeypatch.setenv("IRRELEVANT", "value-three")
        monkeypatch.delenv("TOKEN_X", raising=False)

        assert manager.import_from_env() == 2
        assert manager.get_secret("SECRET_ONE") == "value-one"
        assert manager.get_secret("API_TWO") == "value-two"
        assert manager.get_secret("IRRELEVANT") is None

    def test_import_from_env_with_a_prefix(self, manager: SecretsManager, monkeypatch):
        monkeypatch.setenv("BAHRAM_API_KEY", "prefixed")
        monkeypatch.setenv("OTHER_API_KEY", "not-prefixed")
        assert manager.import_from_env(prefix="BAHRAM_") == 1
        assert manager.get_secret("BAHRAM_API_KEY") == "prefixed"
        assert manager.get_secret("OTHER_API_KEY") is None

    def test_secret_entry_defaults(self):
        entry = SecretEntry(name="n", value="v")
        assert entry.description == ""
        assert entry.category == "general"
        assert entry.created_at == 0.0
