"""Security tests: strict user/session memory isolation.

Verifies that memory, context, and skills are fully isolated between users
and sessions. No mocks — real SemanticMemory, SmartContextManager, and
LearningEngine instances with separate data directories.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from bahram.memory.semantic import SemanticMemory
from bahram.core.smart_context import SmartContextManager
from bahram.autonomy.learning import LearningEngine
from bahram.autonomy.skill_lifecycle import SkillLifecycle


@pytest.fixture(autouse=True)
def _cleanup():
    tmpdirs: list[str] = []
    yield tmpdirs
    for d in tmpdirs:
        shutil.rmtree(d, ignore_errors=True)


def _tmpdir(tmpdirs: list[str]) -> str:
    d = tempfile.mkdtemp()
    tmpdirs.append(d)
    return d


class TestUserAMemoryIsolation:
    """User A stores secret; user B must never see it."""

    def test_user_a_finds_in_own_session(self, _cleanup):
        tmp = _tmpdir(_cleanup)
        mem = SemanticMemory(data_dir=tmp)
        mem.add("secret_a: nuclear launch codes", source="session_a1")

        results = mem.search("secret_a", limit=5)
        assert any("secret_a" in r.content for r in results), (
            "User A should find own memory in own session"
        )

    def test_user_a_finds_in_persistent_memory(self, _cleanup):
        tmp = _tmpdir(_cleanup)
        mem1 = SemanticMemory(data_dir=tmp)
        mem1.add("secret_a: persistent key", source="session_a1")

        # New instance on same dir simulates session A2 for same user
        mem2 = SemanticMemory(data_dir=tmp)
        results = mem2.search("secret_a", limit=5)
        assert any("secret_a" in r.content for r in results), (
            "User A should find memory persisted from session A1 in session A2"
        )

    def test_user_b_does_not_find_a_secret(self, _cleanup):
        tmp_a = _tmpdir(_cleanup)
        tmp_b = _tmpdir(_cleanup)

        mem_a = SemanticMemory(data_dir=tmp_a)
        mem_a.add("secret_a: eyes only", source="session_a1")

        mem_b = SemanticMemory(data_dir=tmp_b)
        results = mem_b.search("secret_a", limit=5)
        assert not any("secret_a" in r.content for r in results), (
            "User B must NOT find user A's memory"
        )

    def test_user_b_search_returns_empty(self, _cleanup):
        tmp_a = _tmpdir(_cleanup)
        tmp_b = _tmpdir(_cleanup)

        mem_a = SemanticMemory(data_dir=tmp_a)
        mem_a.add("classified payload 99", source="session_a1")

        mem_b = SemanticMemory(data_dir=tmp_b)
        ctx = mem_b.get_context("classified payload", max_memories=5)
        assert ctx == ""


class TestSessionMemoryIsolation:
    """Session-specific memories must not leak across sessions of the same user."""

    def test_session_a_retrieves_own_data(self, _cleanup):
        tmp = _tmpdir(_cleanup)
        session_a = SemanticMemory(data_dir=tmp)
        session_a.add("session_a_only: debug flag is on", source="session_a")

        results = session_a.search("session_a_only", limit=5)
        assert any("debug flag" in r.content for r in results)

    def test_session_b_does_not_find_session_a_specific(self, _cleanup):
        tmp_a = _tmpdir(_cleanup)
        tmp_b = _tmpdir(_cleanup)

        session_a = SemanticMemory(data_dir=tmp_a)
        session_a.add("session_a_only: private conversation", source="session_a")

        # Simulate session B (different data_dir = different session)
        session_b = SemanticMemory(data_dir=tmp_b)
        results = session_b.search("session_a_only", limit=5)
        assert not any("private conversation" in r.content for r in results), (
            "Session B must not find session A's session-scoped memory"
        )

    def test_source_tag_preserves_boundary(self, _cleanup):
        tmp_a = _tmpdir(_cleanup)
        tmp_b = _tmpdir(_cleanup)

        SemanticMemory(data_dir=tmp_a).add(
            "classified-alpha-only", source="session_alpha"
        )
        SemanticMemory(data_dir=tmp_b).add(
            "classified-beta-only", source="session_beta"
        )

        results_a = SemanticMemory(data_dir=tmp_a).search("classified", limit=10)
        results_b = SemanticMemory(data_dir=tmp_b).search("classified", limit=10)

        assert any("alpha" in r.content for r in results_a)
        assert not any("beta" in r.content for r in results_a)

        assert any("beta" in r.content for r in results_b)
        assert not any("alpha" in r.content for r in results_b)


class TestSmartContextIsolation:
    """SmartContextManager instances must not leak context across users."""

    def test_user_a_context_not_in_user_b(self, _cleanup):
        ctx_a = SmartContextManager(max_tokens=8192)
        ctx_a.set_system_prompt("User A system prompt")
        ctx_a.add_context("User A private context: bank account 1234", priority=10)
        ctx_a.add_history("user", "Transfer money to myself")

        ctx_b = SmartContextManager(max_tokens=8192)
        ctx_b.set_system_prompt("User B system prompt")
        ctx_b.add_context("User B private context: medical records", priority=10)
        ctx_b.add_history("user", "Schedule appointment")

        messages_a = ctx_a.build_context()
        messages_b = ctx_b.build_context()

        contents_a = " ".join(m["content"] for m in messages_a)
        contents_b = " ".join(m["content"] for m in messages_b)

        assert "bank account 1234" in contents_a
        assert "medical records" not in contents_a

        assert "medical records" in contents_b
        assert "bank account 1234" not in contents_b

    def test_memory_retrieval_scoped_by_user(self, _cleanup):
        tmp_a = _tmpdir(_cleanup)
        tmp_b = _tmpdir(_cleanup)

        mem_a = SemanticMemory(data_dir=tmp_a)
        mem_a.add("User A的记忆: password is hunter2", source="conversation")

        mem_b = SemanticMemory(data_dir=tmp_b)
        mem_b.add("User B的记忆: password is admin123", source="conversation")

        ctx_a = SmartContextManager(max_tokens=8192)
        ctx_a.add_context(mem_a.get_context("password", max_memories=5))

        ctx_b = SmartContextManager(max_tokens=8192)
        ctx_b.add_context(mem_b.get_context("password", max_memories=5))

        built_a = ctx_a.build_context()
        built_b = ctx_b.build_context()

        text_a = " ".join(m["content"] for m in built_a)
        text_b = " ".join(m["content"] for m in built_b)

        assert "hunter2" in text_a
        assert "admin123" not in text_a

        assert "admin123" in text_b
        assert "hunter2" not in text_b

    def test_context_clear_resets_boundary(self, _cleanup):
        ctx = SmartContextManager(max_tokens=8192)
        ctx.add_context("secret: do not leak")
        ctx.add_history("user", "sensitive message")

        ctx.clear()
        messages = ctx.build_context()
        contents = " ".join(m["content"] for m in messages)
        assert "secret" not in contents
        assert "sensitive" not in contents


class TestSkillIsolation:
    """Skills learned by user A must not appear in user B's skill list."""

    def test_skill_a_not_in_user_b(self, _cleanup):
        tmp_a = _tmpdir(_cleanup)
        tmp_b = _tmpdir(_cleanup)

        engine_a = LearningEngine(data_dir=tmp_a)
        engine_b = LearningEngine(data_dir=tmp_b)

        # Manually inject a skill for user A
        from bahram.autonomy.learning import SkillCandidate
        skill = SkillCandidate(
            id="skill_secret_001",
            name="secret_weapon_skill",
            description="Classified skill for user A",
            instructions="Deploy the thing",
            triggers=["deploy", "secret"],
            status="trusted",
        )
        engine_a._skills[skill.id] = skill
        engine_a._save()

        lc_a = SkillLifecycle(learning_engine=engine_a)
        lc_b = SkillLifecycle(learning_engine=engine_b)

        skills_a = lc_a.get_trusted_skills()
        skills_b = lc_b.get_trusted_skills()

        assert any(s.id == "skill_secret_001" for s in skills_a)
        assert not any(s.id == "skill_secret_001" for s in skills_b), (
            "User B must not see user A's skills"
        )

    def test_skill_lifecycle_scoped_by_user(self, _cleanup):
        tmp_a = _tmpdir(_cleanup)
        tmp_b = _tmpdir(_cleanup)

        engine_a = LearningEngine(data_dir=tmp_a)
        engine_b = LearningEngine(data_dir=tmp_b)

        # Generate a skill through user A's engine
        from bahram.autonomy.learning import Lesson
        lesson = Lesson(
            id="lesson_user_a",
            content="Always use async for I/O-bound tasks",
            scope="general",
            source_run="run_a1",
        )
        engine_a._lessons[lesson.id] = lesson
        engine_a._save()

        lc_a = SkillLifecycle(learning_engine=engine_a)
        lc_b = SkillLifecycle(learning_engine=engine_b)

        skills_a = lc_a.get_candidates() + lc_a.get_trusted_skills()
        skills_b = lc_b.get_candidates() + lc_b.get_trusted_skills()

        names_a = {s.name for s in skills_a}
        names_b = {s.name for s in skills_b}

        # A may have generated skills; B must have none from A
        if names_a:
            assert names_a.isdisjoint(names_b), (
                "User A's skill names must not overlap with user B's"
            )

    def test_get_skill_cross_user_denied(self, _cleanup):
        tmp_a = _tmpdir(_cleanup)
        tmp_b = _tmpdir(_cleanup)

        engine_a = LearningEngine(data_dir=tmp_a)
        engine_b = LearningEngine(data_dir=tmp_b)

        from bahram.autonomy.learning import SkillCandidate
        skill = SkillCandidate(
            id="cross_user_skill",
            name="forbidden_knowledge",
            description="Classified",
            instructions="Do stuff",
            triggers=["forbidden"],
        )
        engine_a._skills[skill.id] = skill
        engine_a._save()

        lc_b = SkillLifecycle(learning_engine=engine_b)
        found = lc_b.get_skill("cross_user_skill")
        assert found is None, (
            "User B must not retrieve user A's skill by ID"
        )


class TestCrossBoundaryLeakage:
    """Cross-boundary access attempts must be denied."""

    def test_wrong_user_id_denied(self, _cleanup):
        tmp = _tmpdir(_cleanup)
        mem = SemanticMemory(data_dir=tmp)
        mem.add("user_alpha_secret", source="conversation")

        # Simulate a different user querying
        other_tmp = _tmpdir(_cleanup)
        other_mem = SemanticMemory(data_dir=other_tmp)

        results = other_mem.search("user_alpha_secret", limit=5)
        assert not results, "Wrong user_id must not retrieve memory"

    def test_wrong_session_id_denied(self, _cleanup):
        tmp_a = _tmpdir(_cleanup)
        tmp_b = _tmpdir(_cleanup)

        session_a = SemanticMemory(data_dir=tmp_a)
        session_a.add("session_alpha: classified", source="session_alpha")

        session_b = SemanticMemory(data_dir=tmp_b)
        results = session_b.get("session_alpha: classified")
        # get() takes memory_id not content; use search instead
        results = session_b.search("session_alpha", limit=5)
        assert not results, "Wrong session_id must not retrieve memory"

    def test_subagent_cannot_access_parent_memory(self, _cleanup):
        tmp_parent = _tmpdir(_cleanup)
        tmp_child = _tmpdir(_cleanup)

        parent_mem = SemanticMemory(data_dir=tmp_parent)
        parent_mem.add("parent_private: private API key xyz", source="parent")

        child_mem = SemanticMemory(data_dir=tmp_child)

        # Subagent searches for parent's data — must find nothing
        results = child_mem.search("private API key", limit=5)
        assert not results, "Subagent must not access parent's private memory"

        ctx = child_mem.get_context("private API key", max_memories=5)
        assert ctx == "", "Subagent context must not contain parent memory"

    def test_get_context_cross_user_denied(self, _cleanup):
        tmp_a = _tmpdir(_cleanup)
        tmp_b = _tmpdir(_cleanup)

        mem_a = SemanticMemory(data_dir=tmp_a)
        mem_a.add("user_a_confidential: merger plans", source="user_a")

        mem_b = SemanticMemory(data_dir=tmp_b)
        ctx = mem_b.get_context("merger plans", max_memories=5)
        assert ctx == ""

    def test_delete_does_not_affect_other_users(self, _cleanup):
        tmp_a = _tmpdir(_cleanup)
        tmp_b = _tmpdir(_cleanup)

        mem_a = SemanticMemory(data_dir=tmp_a)
        mem_a.add("user_a_shared_fact", source="user_a")

        mem_b = SemanticMemory(data_dir=tmp_b)
        mem_b.add("user_b_shared_fact", source="user_b")

        # User A deletes their memory
        results = mem_a.search("shared_fact", limit=5)
        for r in results:
            mem_a.delete(r.id)

        # User B's memory must be untouched
        results_b = mem_b.search("shared_fact", limit=5)
        assert len(results_b) > 0, "User A's delete must not affect user B"

    def test_metadata_not_leaked_across_instances(self, _cleanup):
        tmp_a = _tmpdir(_cleanup)
        tmp_b = _tmpdir(_cleanup)

        mem_a = SemanticMemory(data_dir=tmp_a)
        mem_a.add("sensitive data", source="user_a", metadata={"user": "alice"})

        mem_b = SemanticMemory(data_dir=tmp_b)
        stats_b = mem_b.get_statistics()
        assert stats_b["total_memories"] == 0
        assert stats_b["sources"] == []
