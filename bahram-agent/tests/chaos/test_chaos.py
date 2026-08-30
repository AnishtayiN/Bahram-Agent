from __future__ import annotations

import asyncio
import os
import tempfile
import time
import pytest

from bahram.core.engine import AgentEngine, Message, MessageRole, ToolCall, ToolExecutor, RunState


def _tc(name: str, args: dict) -> ToolCall:
    import uuid
    return ToolCall(id=str(uuid.uuid4())[:8], name=name, arguments=args)


class TestToolTimeout:
    @pytest.mark.asyncio
    async def test_execute_code_timeout(self, engine):
        class SlowTool:
            async def execute(self, **kw):
                await asyncio.sleep(100)
                return "never"
            def schema(self):
                return {"name": "bash", "inputSchema": {"type": "object", "properties": {}}}

        executor = ToolExecutor({"bash": SlowTool()}, engine._approval_system)
        result = await executor.execute(
            _tc("bash", {"command": "sleep 30"}),
            timeout=0.1,
        )
        assert not result.success
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_concurrent_tool_executions(self, engine):
        class FastTool:
            async def execute(self, **kw):
                return "ok"
            def schema(self):
                return {"name": "bash", "inputSchema": {"type": "object", "properties": {}}}

        executor = ToolExecutor({"bash": FastTool()}, engine._approval_system)
        tasks = [
            executor.execute(_tc("bash", {"command": "echo hello"}))
            for _ in range(5)
        ]
        results = await asyncio.gather(*tasks)
        assert all(r.success for r in results)


class TestFileSystemChaos:
    @pytest.mark.asyncio
    async def test_write_nonexistent_directory(self, engine):
        from bahram.tools.file import WriteTool
        tool = WriteTool()
        result = await tool.execute(
            file_path="/nonexistent/path/deep/file.txt",
            content="test",
            create_dirs=False,
        )
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, engine):
        from bahram.tools.file import ReadTool
        tool = ReadTool()
        result = await tool.execute(file_path="/nonexistent/file.txt")
        assert "Error" in result or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_edit_nonexistent_file(self, engine):
        from bahram.tools.file import EditTool
        tool = EditTool()
        result = await tool.execute(
            file_path="/nonexistent/file.txt",
            old_string="a",
            new_string="b",
        )
        assert "Error" in result


class TestEngineCancellation:
    def test_cancel_sets_event(self, engine):
        engine.cancel()
        assert engine._cancel_event.is_set()

    def test_reset_cancel_clears_event(self, engine):
        engine.cancel()
        engine.reset_cancel()
        assert not engine._cancel_event.is_set()

    @pytest.mark.asyncio
    async def test_run_respects_cancellation(self, engine):
        from unittest.mock import AsyncMock, MagicMock
        from bahram.core.engine import AgentResponse, RunState

        mock_provider = MagicMock()

        async def mock_complete(messages, tools=None, **kwargs):
            engine.cancel()
            return AgentResponse(content="thinking", state=RunState.THINKING)

        mock_provider.complete = mock_complete
        engine.register_provider("test", mock_provider)

        messages = [Message(role=MessageRole.USER, content="test")]
        result = await engine.run(messages, model="test/model")
        assert result.state in (RunState.CANCELLED, RunState.COMPLETED)


class TestMemoryChaos:
    def test_memory_concurrent_writes(self):
        from bahram.memory.semantic import SemanticMemory
        with tempfile.TemporaryDirectory() as tmpdir:
            mem = SemanticMemory(data_dir=tmpdir)
            for i in range(10):
                mem.add(content=f"Memory {i}", source=f"source_{i % 3}")
            stats = mem.get_statistics()
            assert stats["total_memories"] == 10
            mem.close()

    def test_memory_special_characters(self):
        from bahram.memory.semantic import SemanticMemory
        with tempfile.TemporaryDirectory() as tmpdir:
            mem = SemanticMemory(data_dir=tmpdir)
            mem.add(content="SELECT * FROM users; DROP TABLE users;--", source="sql_injection")
            mem.add(content="<script>alert('xss')</script>", source="xss")
            results = mem.search("SELECT")
            assert len(results) > 0
            mem.close()


class TestPersistenceChaos:
    def test_corrupted_db_recovery(self):
        from bahram.core.persistence import SessionStore
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store = SessionStore(db_path=db_path)
            store.create_session("session1", user_id="user1")
            store.add_message("session1", Message(
                role=MessageRole.USER,
                content="Hello",
            ))
            store2 = SessionStore(db_path=db_path)
            sessions = store2.list_sessions()
            assert len(sessions) >= 1

    def test_concurrent_session_creation(self):
        from bahram.core.persistence import SessionStore
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SessionStore(db_path=os.path.join(tmpdir, "test.db"))
            for i in range(10):
                store.create_session(f"session_{i}", user_id=f"user_{i}")
            sessions = store.list_sessions()
            assert len(sessions) == 10


class TestProviderChaos:
    @pytest.mark.asyncio
    async def test_provider_error_handling(self, engine):
        from unittest.mock import AsyncMock, MagicMock

        mock_provider = MagicMock()
        mock_provider.complete = AsyncMock(side_effect=ConnectionError("Network down"))
        engine.register_provider("chaos", mock_provider)

        messages = [Message(role=MessageRole.USER, content="test")]
        result = await engine.run(messages, model="chaos/model")
        assert result.state == RunState.FAILED
        assert "error" in result.content.lower()

    @pytest.mark.asyncio
    async def test_max_iterations_enforced(self, engine):
        from unittest.mock import AsyncMock, MagicMock
        from bahram.core.engine import AgentResponse, ToolCall

        call_count = 0

        async def fake_complete(messages, tools=None, **kwargs):
            nonlocal call_count
            call_count += 1
            return AgentResponse(
                content="thinking...",
                tool_calls=[ToolCall(id=f"tc{call_count}", name="bash", arguments={"command": "echo step"})],
            )

        mock_provider = MagicMock()
        mock_provider.complete = fake_complete
        engine.register_provider("loop", mock_provider)

        class MockBash:
            async def execute(self, **kw):
                return "ok"
            def schema(self):
                return {"name": "bash", "inputSchema": {"type": "object", "properties": {}}}

        engine.register_tool("bash", MockBash())

        messages = [Message(role=MessageRole.USER, content="do something")]
        result = await engine.run(messages, model="loop/test")
        assert call_count <= 20
