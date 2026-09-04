from __future__ import annotations

from bahram.core.engine import Message, MessageRole
from bahram.core.persistence import SessionStore


class TestSessionStore:
    def test_init(self, tmp_path):
        store = SessionStore(db_path=str(tmp_path / "test.db"))
        assert store is not None

    def test_create_session(self, tmp_path):
        store = SessionStore(db_path=str(tmp_path / "test.db"))
        session = store.create_session("test-123", user_id="user1", channel="telegram")
        assert session["id"] == "test-123"

    def test_get_session(self, tmp_path):
        store = SessionStore(db_path=str(tmp_path / "test.db"))
        store.create_session("test-123")
        session = store.get_session("test-123")
        assert session is not None
        assert session["id"] == "test-123"

    def test_get_nonexistent(self, tmp_path):
        store = SessionStore(db_path=str(tmp_path / "test.db"))
        assert store.get_session("nonexistent") is None

    def test_add_message(self, tmp_path):
        store = SessionStore(db_path=str(tmp_path / "test.db"))
        store.create_session("test-123")
        msg = Message(role=MessageRole.USER, content="Hello")
        msg_id = store.add_message("test-123", msg)
        assert msg_id is not None

    def test_get_messages(self, tmp_path):
        store = SessionStore(db_path=str(tmp_path / "test.db"))
        store.create_session("test-123")
        store.add_message("test-123", Message(role=MessageRole.USER, content="Hello"))
        store.add_message("test-123", Message(role=MessageRole.ASSISTANT, content="Hi"))
        messages = store.get_messages("test-123")
        assert len(messages) == 2
        assert messages[0].content == "Hello"
        assert messages[1].content == "Hi"

    def test_delete_session(self, tmp_path):
        store = SessionStore(db_path=str(tmp_path / "test.db"))
        store.create_session("test-123")
        store.add_message("test-123", Message(role=MessageRole.USER, content="Hello"))
        store.delete_session("test-123")
        assert store.get_session("test-123") is None
        assert len(store.get_messages("test-123")) == 0

    def test_list_sessions(self, tmp_path):
        store = SessionStore(db_path=str(tmp_path / "test.db"))
        store.create_session("s1", user_id="u1")
        store.create_session("s2", user_id="u2")
        sessions = store.list_sessions()
        assert len(sessions) == 2

    def test_persistence(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        store1 = SessionStore(db_path=db_path)
        store1.create_session("test-123")
        store1.add_message("test-123", Message(role=MessageRole.USER, content="Hello"))

        store2 = SessionStore(db_path=db_path)
        messages = store2.get_messages("test-123")
        assert len(messages) == 1
        assert messages[0].content == "Hello"

    def test_clear_messages(self, tmp_path):
        store = SessionStore(db_path=str(tmp_path / "test.db"))
        store.create_session("test-123")
        store.add_message("test-123", Message(role=MessageRole.USER, content="Hello"))
        store.clear_messages("test-123")
        assert len(store.get_messages("test-123")) == 0
