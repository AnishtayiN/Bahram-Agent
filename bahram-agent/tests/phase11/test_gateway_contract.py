"""Phase 11: Gateway contract tests.

Tests the gateway service for request routing, session management,
authorization, cancellation, and response normalization.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from bahram.core.agent import Agent, Session
from bahram.core.config import Config
from bahram.core.engine import Message, MessageRole


class FakeGateway:
    """Minimal gateway implementation for testing contract behavior."""

    def __init__(self, agent: Agent):
        self._agent = agent
        self._sessions: dict[str, str] = {}
        self._authorization: dict[str, list[str]] = {}
        self._request_log: list[dict] = []

    def set_allowed_users(self, session_id: str, user_ids: list[str]):
        self._authorization[session_id] = user_ids

    def is_authorized(self, session_id: str, user_id: str) -> bool:
        if session_id not in self._authorization:
            return True
        return user_id in self._authorization[session_id]

    def create_session(self, user_id: str = "") -> str:
        session = self._agent.create_session(metadata={"user_id": user_id})
        self._sessions[session.id] = user_id
        return session.id

    def route_request(self, session_id: str, user_id: str, message: str) -> dict:
        self._request_log.append({
            "session_id": session_id,
            "user_id": user_id,
            "message": message,
        })

        if not self.is_authorized(session_id, user_id):
            return {"error": "Unauthorized", "status": 403}

        if session_id not in self._sessions and not self._agent.get_session(session_id):
            return {"error": "Session not found", "status": 404}

        return {
            "status": 200,
            "session_id": session_id,
            "message": message,
        }

    def cancel_session(self, session_id: str) -> dict:
        self._agent.engine.cancel()
        return {"status": 200, "cancelled": session_id}

    def normalize_response(self, raw_response: dict) -> dict:
        return {
            "content": raw_response.get("content", ""),
            "state": raw_response.get("state", "unknown"),
            "session_id": raw_response.get("session_id", ""),
            "metadata": raw_response.get("metadata", {}),
        }


class TestGatewayContract:
    """Test gateway contract behavior."""

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

    def test_session_creation(self):
        """Gateway should create sessions."""
        agent = self._make_agent()
        gw = FakeGateway(agent)

        session_id = gw.create_session(user_id="user_1")

        assert session_id is not None
        assert len(session_id) > 0
        assert agent.get_session(session_id) is not None

    def test_session_resume(self):
        """Gateway should resume existing sessions."""
        agent = self._make_agent()
        gw = FakeGateway(agent)

        session_id = gw.create_session(user_id="user_1")

        result = gw.route_request(session_id, "user_1", "hello")
        assert result["status"] == 200
        assert result["session_id"] == session_id

    def test_concurrent_sessions(self):
        """Gateway should handle multiple concurrent sessions."""
        agent = self._make_agent()
        gw = FakeGateway(agent)

        sessions = []
        for i in range(5):
            sid = gw.create_session(user_id=f"user_{i}")
            sessions.append(sid)

        assert len(set(sessions)) == 5

        for i, sid in enumerate(sessions):
            result = gw.route_request(sid, f"user_{i}", f"message from user {i}")
            assert result["status"] == 200

    def test_authorization_blocks_unauthorized(self):
        """Gateway should block unauthorized users."""
        agent = self._make_agent()
        gw = FakeGateway(agent)

        session_id = gw.create_session(user_id="admin")
        gw.set_allowed_users(session_id, ["admin"])

        result = gw.route_request(session_id, "attacker", "malicious message")
        assert result["status"] == 403
        assert "error" in result

    def test_authorization_allows_authorized(self):
        """Gateway should allow authorized users."""
        agent = self._make_agent()
        gw = FakeGateway(agent)

        session_id = gw.create_session(user_id="admin")
        gw.set_allowed_users(session_id, ["admin", "trusted"])

        result = gw.route_request(session_id, "admin", "legitimate message")
        assert result["status"] == 200

    def test_cancellation(self):
        """Gateway should support cancellation."""
        agent = self._make_agent()
        gw = FakeGateway(agent)

        session_id = gw.create_session(user_id="user_1")

        result = gw.cancel_session(session_id)
        assert result["status"] == 200
        assert result["cancelled"] == session_id

    def test_response_normalization(self):
        """Gateway should normalize responses."""
        agent = self._make_agent()
        gw = FakeGateway(agent)

        raw = {"content": "hello", "state": "completed", "session_id": "s1", "metadata": {"key": "val"}}
        normalized = gw.normalize_response(raw)

        assert "content" in normalized
        assert "state" in normalized
        assert "session_id" in normalized
        assert "metadata" in normalized

    def test_request_logging(self):
        """Gateway should log all requests."""
        agent = self._make_agent()
        gw = FakeGateway(agent)

        session_id = gw.create_session(user_id="user_1")

        gw.route_request(session_id, "user_1", "message 1")
        gw.route_request(session_id, "user_1", "message 2")

        assert len(gw._request_log) == 2
        assert gw._request_log[0]["message"] == "message 1"
        assert gw._request_log[1]["message"] == "message 2"

    def test_session_not_found(self):
        """Gateway should return error for nonexistent session."""
        agent = self._make_agent()
        gw = FakeGateway(agent)

        result = gw.route_request("nonexistent", "user_1", "hello")
        assert result["status"] == 404

    def test_user_session_mapping(self):
        """Gateway should track user-session mappings."""
        agent = self._make_agent()
        gw = FakeGateway(agent)

        s1 = gw.create_session(user_id="alice")
        s2 = gw.create_session(user_id="bob")

        assert gw._sessions[s1] == "alice"
        assert gw._sessions[s2] == "bob"
        assert s1 != s2
