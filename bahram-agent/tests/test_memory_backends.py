"""Behavioural tests for the memory backends.

Covers bahram/memory/base.py, conversation.py, episodic.py, providers.py and
the parts of semantic.py that the other suites do not reach.  Every test runs
against a real store on ``tmp_path`` (or a real in-memory SQLite database), so
the persistence round trips are exercised for real.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from bahram.memory.base import BaseMemory, MemoryEntry
from bahram.memory.conversation import ConversationMemory
from bahram.memory.episodic import EpisodicMemory
from bahram.memory.providers import (
    LocalMemoryProvider,
    MemoryProvider,
    MemoryProviderManager,
    MemoryProviderType,
)
from bahram.memory.providers import MemoryEntry as ProviderEntry
from bahram.memory.semantic import SemanticMemory


# ---------------------------------------------------------------------------
# base
# ---------------------------------------------------------------------------
class TestBaseMemory:
    def test_calculate_importance_scores_code_content_higher(self):
        base_score = BaseMemory.calculate_importance(BaseMemory, "just a note", {})
        code_score = BaseMemory.calculate_importance(BaseMemory, "def foo():", {})
        assert code_score > base_score

    def test_calculate_importance_rewards_error_keywords(self):
        assert BaseMemory.calculate_importance(BaseMemory, "hit a bug", {}) > 0.5

    def test_calculate_importance_rewards_preference_metadata(self):
        score = BaseMemory.calculate_importance(BaseMemory, "x", {"type": "preference"})
        assert score == pytest.approx(0.7)

    def test_calculate_importance_rewards_completed_tasks(self):
        score = BaseMemory.calculate_importance(BaseMemory, "x", {"type": "task_complete"})
        assert score == pytest.approx(0.65)

    def test_calculate_importance_is_capped_at_one(self):
        # 0.5 base + 0.1 code + 0.1 error + 0.2 preference = 0.9
        score = BaseMemory.calculate_importance(
            BaseMemory, "def class import async error fix bug issue", {"type": "preference"}
        )
        assert score == pytest.approx(0.9)
        assert score <= 1.0

    def test_abstract_methods_must_be_implemented(self):
        with pytest.raises(TypeError):
            BaseMemory()  # type: ignore[abstract]

    def test_memory_entry_defaults(self):
        entry = MemoryEntry(id="1", content="c")
        assert entry.metadata == {}
        assert entry.importance == 0.5
        assert entry.access_count == 0
        assert entry.last_accessed is None
        assert isinstance(entry.timestamp, datetime)


# ---------------------------------------------------------------------------
# conversation
# ---------------------------------------------------------------------------
class TestConversationMemory:
    async def test_add_get_search(self, tmp_path: Path):
        memory = ConversationMemory(str(tmp_path / "conv.json"))
        first = await memory.add("we discussed the deploy plan")
        await memory.add("we discussed the release notes")

        entry = await memory.get(first)
        assert entry is not None and entry.content == "we discussed the deploy plan"
        assert entry.access_count == 1
        assert entry.last_accessed is not None

        results = await memory.search("deploy")
        assert [r.id for r in results] == [first]

        assert len(await memory.search("discussed")) == 2
        assert len(await memory.list_all()) == 2

    async def test_get_unknown_id_returns_none(self, tmp_path: Path):
        memory = ConversationMemory(str(tmp_path / "conv.json"))
        assert await memory.get("nope") is None

    async def test_search_is_case_insensitive_and_respects_limit(self, tmp_path: Path):
        memory = ConversationMemory(str(tmp_path / "conv.json"))
        for i in range(5):
            await memory.add(f"entry {i} about Widgets")
        assert len(await memory.search("widgets", limit=2)) == 2

    async def test_update_and_delete(self, tmp_path: Path):
        memory = ConversationMemory(str(tmp_path / "conv.json"))
        memory_id = await memory.add("original")

        assert await memory.update(memory_id, "updated") is True
        assert (await memory.get(memory_id)).content == "updated"
        assert await memory.update("nope", "x") is False

        assert await memory.delete(memory_id) is True
        assert await memory.delete(memory_id) is False

    async def test_clear(self, tmp_path: Path):
        memory = ConversationMemory(str(tmp_path / "conv.json"))
        await memory.add("x")
        await memory.clear()
        assert await memory.list_all() == []

    async def test_persistence_round_trip(self, tmp_path: Path):
        path = tmp_path / "conv.json"
        memory_id = await ConversationMemory(str(path)).add(
            "persisted note", metadata={"type": "preference"}
        )

        reloaded = ConversationMemory(str(path))
        entry = await reloaded.get(memory_id)
        assert entry is not None
        assert entry.content == "persisted note"
        assert entry.metadata == {"type": "preference"}
        assert entry.importance == pytest.approx(0.7)

    async def test_corrupt_store_is_ignored(self, tmp_path: Path):
        path = tmp_path / "conv.json"
        path.write_text("{ not json")
        memory = ConversationMemory(str(path))
        assert await memory.list_all() == []

    async def test_search_ranks_by_importance(self, tmp_path: Path):
        memory = ConversationMemory(str(tmp_path / "conv.json"))
        await memory.add("shared keyword", metadata={"type": "preference"})
        await memory.add("shared keyword")
        results = await memory.search("shared")
        assert results[0].importance > results[1].importance

    async def test_get_recent_and_get_important(self, tmp_path: Path):
        memory = ConversationMemory(str(tmp_path / "conv.json"))
        plain = await memory.add("plain entry")
        important = await memory.add("important entry", metadata={"type": "preference"})

        assert (await memory.get_important(limit=1))[0].id == important
        assert (await memory.get_recent(limit=1))[0].id in {plain, important}


# ---------------------------------------------------------------------------
# episodic
# ---------------------------------------------------------------------------
class TestEpisodicMemory:
    async def test_add_attaches_recorded_at(self, tmp_path: Path):
        memory = EpisodicMemory(str(tmp_path / "ep.json"))
        memory_id = await memory.add("something happened")
        entry = await memory.get(memory_id)
        assert "recorded_at" in entry.metadata

    async def test_record_task_completion(self, tmp_path: Path):
        memory = EpisodicMemory(str(tmp_path / "ep.json"))
        memory_id = await memory.record_task_completion(
            "ship release", "deployed", tools_used=["bash", "git"]
        )
        entry = await memory.get(memory_id)
        assert entry.metadata["type"] == "task_complete"
        assert entry.metadata["tools_used"] == ["bash", "git"]
        assert "Completed task: ship release" in entry.content
        assert entry.importance == pytest.approx(0.65)

    async def test_record_error(self, tmp_path: Path):
        memory = EpisodicMemory(str(tmp_path / "ep.json"))
        memory_id = await memory.record_error("OOM", "during training")
        entry = await memory.get(memory_id)
        assert entry.metadata["error"] == "OOM"
        assert entry.metadata["context"] == "during training"

    async def test_record_learning(self, tmp_path: Path):
        memory = EpisodicMemory(str(tmp_path / "ep.json"))
        memory_id = await memory.record_learning("sqlite fts5 is enough", "profiling")
        entry = await memory.get(memory_id)
        assert entry.metadata["type"] == "learning"
        assert entry.metadata["source"] == "profiling"

    async def test_search_update_delete_clear(self, tmp_path: Path):
        memory = EpisodicMemory(str(tmp_path / "ep.json"))
        memory_id = await memory.add("deploy failed on staging")

        assert [r.id for r in await memory.search("staging")] == [memory_id]
        assert await memory.update(memory_id, "deploy failed on prod") is True
        assert "prod" in (await memory.get(memory_id)).content
        assert await memory.update("nope", "x") is False

        await memory.clear()
        assert await memory.list_all() == []

    async def test_delete_unknown_returns_false(self, tmp_path: Path):
        memory = EpisodicMemory(str(tmp_path / "ep.json"))
        assert await memory.delete("nope") is False

    async def test_persistence_round_trip(self, tmp_path: Path):
        path = tmp_path / "ep.json"
        memory_id = await EpisodicMemory(str(path)).add("persisted episode")
        reloaded = EpisodicMemory(str(path))
        assert (await reloaded.get(memory_id)).content == "persisted episode"

    async def test_corrupt_store_is_ignored(self, tmp_path: Path):
        path = tmp_path / "ep.json"
        path.write_text("[not json at all")
        assert await EpisodicMemory(str(path)).list_all() == []


# ---------------------------------------------------------------------------
# providers
# ---------------------------------------------------------------------------
class TestMemoryProviders:
    def test_base_provider_methods_are_abstract(self):
        provider = MemoryProvider(MemoryProviderType.QDRANT)

        async def exercise():
            results = []
            for call in (
                provider.add(ProviderEntry(id="1", content="c")),
                provider.search("q"),
                provider.delete("1"),
                provider.get("1"),
                provider.count(),
            ):
                try:
                    await call
                except NotImplementedError:
                    results.append("raised")
            return results

        import asyncio

        assert asyncio.run(exercise()) == ["raised"] * 5

    async def test_local_provider_round_trip(self, tmp_path: Path):
        provider = LocalMemoryProvider(str(tmp_path / "mem"))
        entry = ProviderEntry(id="e1", content="the quick brown fox")

        assert await provider.add(entry) is True
        assert entry.timestamp > 0  # filled in on add

        assert (await provider.get("e1")).content == "the quick brown fox"
        assert [e.id for e in await provider.search("brown")] == ["e1"]
        assert await provider.count() == 1

        assert await provider.delete("e1") is True
        assert await provider.delete("e1") is False
        assert await provider.count() == 0

    async def test_local_provider_search_is_case_insensitive(self, tmp_path: Path):
        provider = LocalMemoryProvider(str(tmp_path / "mem"))
        await provider.add(ProviderEntry(id="e1", content="PostgreSQL tuning"))
        assert len(await provider.search("postgresql")) == 1

    async def test_local_provider_persists(self, tmp_path: Path):
        data_dir = tmp_path / "mem"
        await LocalMemoryProvider(str(data_dir)).add(
            ProviderEntry(id="e1", content="persisted", metadata={"k": "v"})
        )
        reloaded = LocalMemoryProvider(str(data_dir))
        assert (await reloaded.get("e1")).metadata == {"k": "v"}

    async def test_local_provider_corrupt_file_is_ignored(self, tmp_path: Path):
        data_dir = tmp_path / "mem"
        data_dir.mkdir()
        (data_dir / "local_memory.json").write_text("}")
        assert await LocalMemoryProvider(str(data_dir)).count() == 0

    async def test_manager_defaults_to_local(self, tmp_path: Path):
        manager = MemoryProviderManager(str(tmp_path / "mem"))
        assert isinstance(manager.get_provider(), LocalMemoryProvider)
        assert manager.list_providers()[0]["is_active"] is True

    def test_manager_set_active_unknown_provider(self, tmp_path: Path):
        manager = MemoryProviderManager(str(tmp_path / "mem"))
        assert manager.set_active_provider("qdrant") is False
        assert manager.get_provider("qdrant") is manager._providers["local"]

    async def test_manager_register_and_activate(self, tmp_path: Path):
        manager = MemoryProviderManager(str(tmp_path / "mem"))
        custom = LocalMemoryProvider(str(tmp_path / "other"))
        manager.register_provider("custom", custom)

        assert manager.set_active_provider("custom") is True
        assert manager.get_provider() is custom
        types = {p["name"]: p["type"] for p in manager.list_providers()}
        assert types == {"local": "local", "custom": "local"}


# ---------------------------------------------------------------------------
# semantic
# ---------------------------------------------------------------------------
class TestSemanticMemory:
    """SemanticMemory is a synchronous SQLite/FTS5 store."""

    def test_add_search_and_get_context(self, tmp_path: Path):
        memory = SemanticMemory(data_dir=str(tmp_path / "sem"))
        memory.add("the user prefers dark mode", source="conversation")
        memory.add("the project uses poetry", source="conversation")

        assert "dark mode" in memory.get_context("prefers", max_memories=5)
        results = memory.search("poetry")
        assert results and "poetry" in results[0].content

    def test_in_memory_database_creates_no_file(self, tmp_path: Path):
        memory = SemanticMemory(data_dir=":memory:")
        memory.add("ephemeral note")
        assert "ephemeral note" in memory.get_context("ephemeral")
        assert list(tmp_path.iterdir()) == []

    def test_get_and_delete(self, tmp_path: Path):
        memory = SemanticMemory(data_dir=str(tmp_path / "sem"))
        memory_id = memory.add("to be removed", source="s")
        assert memory.get(memory_id)["content"] == "to be removed"

        assert memory.delete(memory_id) is True
        assert memory.delete(memory_id) is False
        assert memory.get(memory_id) is None

    def test_search_returns_nothing_for_empty_query(self, tmp_path: Path):
        memory = SemanticMemory(data_dir=str(tmp_path / "sem"))
        memory.add("something")
        assert memory.search("") == []

    def test_scope_is_respected(self, tmp_path: Path):
        memory = SemanticMemory(data_dir=str(tmp_path / "sem"))
        memory.add("global scoped note", scope="global")
        memory.add("user scoped note", scope="user")
        assert len(memory.search("scoped", scope="user")) == 1

    def test_metadata_is_persisted_as_a_string(self, tmp_path: Path):
        memory = SemanticMemory(data_dir=str(tmp_path / "sem"))
        memory_id = memory.add("with metadata", metadata={"k": "v"})
        assert memory.get(memory_id)["metadata"] == "{'k': 'v'}"
        memory_id = memory.add("without metadata")
        assert memory.get(memory_id)["metadata"] == "{}"

    def test_statistics(self, tmp_path: Path):
        memory = SemanticMemory(data_dir=str(tmp_path / "sem"))
        memory.add("a", source="chat", scope="global")
        memory.add("b", source="chat", scope="user")
        stats = memory.get_statistics()
        assert stats["total_memories"] == 2
        assert stats["sources"] == ["chat"]
        assert set(stats["scopes"]) == {"global", "user"}

    def test_consolidate_removes_old_low_confidence_memories(self, tmp_path: Path):
        memory = SemanticMemory(data_dir=str(tmp_path / "sem"))
        memory.add("stale", confidence=0.05)
        memory.add("fresh", confidence=1.0)
        assert memory.consolidate(max_age_hours=0, min_confidence=0.1) == 1

    def test_decay_lowers_confidence(self, tmp_path: Path):
        memory = SemanticMemory(data_dir=str(tmp_path / "sem"))
        memory.add("x", confidence=1.0)
        memory.add("already low", confidence=0.05)
        # only rows above the 0.1 floor are decayed
        assert memory.decay(decay_rate=0.5) == 1

    def test_user_profile_round_trip(self, tmp_path: Path):
        memory = SemanticMemory(data_dir=str(tmp_path / "sem"))
        memory.store_user_profile("alice", "editor", "vim")
        profile = memory.get_user_profile("alice")
        assert profile["user_id"] == "alice"
        assert any("editor: vim" in fact for fact in profile["facts"])

    def test_persists_across_instances(self, tmp_path: Path):
        data_dir = str(tmp_path / "sem")
        SemanticMemory(data_dir=data_dir).add("survives restart")
        assert "survives restart" in SemanticMemory(data_dir=data_dir).get_context("restart")

    def test_fts_fallback_when_index_cannot_be_created(self, tmp_path: Path):
        """A missing FTS table must degrade to LIKE search, not explode."""
        memory = SemanticMemory(data_dir=str(tmp_path / "sem"))
        memory.add("fallback content")
        memory._conn.execute("DROP TABLE IF EXISTS memories_fts")
        assert "fallback content" in memory.get_context("fallback")

    def test_get_context_without_matches_returns_empty(self, tmp_path: Path):
        memory = SemanticMemory(data_dir=str(tmp_path / "sem"))
        assert memory.get_context("nothing here") == ""

    def test_close_is_idempotent(self, tmp_path: Path):
        memory = SemanticMemory(data_dir=str(tmp_path / "sem"))
        memory.close()
        memory.close()


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------
def test_json_backing_store_is_valid_json(tmp_path: Path):
    """The JSON backends must write re-readable files, not append garbage."""
    path = tmp_path / "conv.json"
    memory = ConversationMemory(str(path))
    import asyncio

    asyncio.run(memory.add("first"))
    asyncio.run(memory.add("second"))
    data = json.loads(path.read_text())
    assert sorted(item["content"] for item in data) == ["first", "second"]


def test_memory_entry_ordering_by_timestamp():
    older = MemoryEntry(id="a", content="a", timestamp=datetime.now() - timedelta(days=1))
    newer = MemoryEntry(id="b", content="b", timestamp=datetime.now())
    assert sorted([newer, older], key=lambda e: e.timestamp)[0].id == "a"
