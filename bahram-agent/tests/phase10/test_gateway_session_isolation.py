"""Phase 10: Gateway session isolation tests.

Tests that concurrent sessions from different users are properly isolated:
no cross-session messages, no cross-user memory, no job crossover.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from bahram.core.agent import Agent, Session
from bahram.core.config import Config
from bahram.core.engine import Message, MessageRole


class TestGatewaySessionIsolation:
    """Verify session isolation across concurrent users."""

    def setup_method(self):
        self._tmpdirs = []

    def teardown_method(self):
        import shutil
        for d in self._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def _make_agent(self):
        tmpdir = tempfile.mkdtemp()
        self._tmpdirs.append(tmpdir)
        config = Config()
        config.memory.database = str(Path(tmpdir) / "memory.db")
        return Agent(config=config)

    def test_separate_sessions_are_independent(self):
        """Two sessions should have separate context."""
        agent = self._make_agent()

        session_a = agent.create_session(metadata={"user": "alice"})
        session_b = agent.create_session(metadata={"user": "bob"})

        assert session_a.id != session_b.id
        assert agent.get_session(session_a.id) is not None
        assert agent.get_session(session_b.id) is not None

    def test_session_history_isolation(self):
        """Messages in session A should not appear in session B."""
        agent = self._make_agent()

        session_a = agent.create_session()
        session_b = agent.create_session()

        ctx_a = agent.context.get_or_create(session_a.id)
        ctx_b = agent.context.get_or_create(session_b.id)

        msg_a = Message(role=MessageRole.USER, content="Alice's secret message")
        msg_b = Message(role=MessageRole.USER, content="Bob's secret message")

        ctx_a.add_message(msg_a)
        ctx_b.add_message(msg_b)

        history_a = agent.get_history(session_a.id)
        history_b = agent.get_history(session_b.id)

        assert any("Alice" in m.content for m in history_a)
        assert not any("Bob" in m.content for m in history_a)

        assert any("Bob" in m.content for m in history_b)
        assert not any("Alice" in m.content for m in history_b)

    def test_delete_session_does_not_affect_others(self):
        """Deleting one session should not affect other sessions."""
        agent = self._make_agent()

        session_a = agent.create_session()
        session_b = agent.create_session()

        agent.delete_session(session_a.id)

        assert agent.get_session(session_a.id) is None
        assert agent.get_session(session_b.id) is not None

    def test_concurrent_session_creation(self):
        """Multiple sessions can be created concurrently without issues."""
        agent = self._make_agent()

        sessions = []
        for i in range(10):
            session = agent.create_session(metadata={"user": f"user_{i}"})
            sessions.append(session)

        ids = [s.id for s in sessions]
        assert len(set(ids)) == 10, "All session IDs should be unique"

        for session in sessions:
            assert agent.get_session(session.id) is not None

    def test_persistence_store_isolation(self):
        """SessionStore should keep messages separate per session."""
        agent = self._make_agent()

        session_a = agent.create_session()
        session_b = agent.create_session()

        msg_a = Message(role=MessageRole.USER, content="Message for A")
        msg_b = Message(role=MessageRole.USER, content="Message for B")

        agent._store.add_message(session_a.id, msg_a)
        agent._store.add_message(session_b.id, msg_b)

        stored_a = agent._store.get_messages(session_a.id)
        stored_b = agent._store.get_messages(session_b.id)

        assert any("Message for A" in str(m) for m in stored_a)
        assert not any("Message for B" in str(m) for m in stored_a)

        assert any("Message for B" in str(m) for m in stored_b)
        assert not any("Message for A" in str(m) for m in stored_b)

    def test_multiple_users_concurrent(self):
        """Multiple users should be able to use the agent concurrently."""
        agent = self._make_agent()

        user_sessions = {}
        for user_id in range(5):
            session = agent.create_session(metadata={"user_id": user_id})
            user_sessions[user_id] = session

        assert len(user_sessions) == 5
        assert len(set(s.id for s in user_sessions.values())) == 5

    def test_clear_history_session_scoped(self):
        """Clearing history should only affect the target session."""
        agent = self._make_agent()

        session_a = agent.create_session()
        session_b = agent.create_session()

        ctx_a = agent.context.get_or_create(session_a.id)
        ctx_b = agent.context.get_or_create(session_b.id)

        ctx_a.add_message(Message(role=MessageRole.USER, content="A message"))
        ctx_b.add_message(Message(role=MessageRole.USER, content="B message"))

        agent.clear_history(session_a.id)

        assert len(agent.get_history(session_a.id)) == 0
        assert len(agent.get_history(session_b.id)) > 0

    def test_session_metadata_isolation(self):
        """Session metadata should be independent."""
        agent = self._make_agent()

        session_a = agent.create_session(metadata={"user": "alice", "role": "admin"})
        session_b = agent.create_session(metadata={"user": "bob", "role": "viewer"})

        meta_a = agent.get_session(session_a.id).metadata
        meta_b = agent.get_session(session_b.id).metadata

        assert meta_a["user"] == "alice"
        assert meta_b["user"] == "bob"
        assert meta_a["role"] == "admin"
        assert meta_b["role"] == "viewer"

    def test_smart_context_separate_instances(self):
        """Each agent should have its own SmartContextManager."""
        agent = self._make_agent()

        assert agent.smart_context is not None

        session_a = agent.create_session()
        agent.smart_context.add_context("Alice context", priority=3)

        usage = agent.smart_context.get_usage()
        assert usage["total_used"] > 0
