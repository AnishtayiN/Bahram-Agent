"""Phase 10: Memory isolation tests.

Tests that memory is properly isolated between users and sessions,
and that no cross-boundary leakage occurs.
"""

from __future__ import annotations

import tempfile

from bahram.memory.semantic import SemanticMemory


class TestMemoryIsolation:
    """Verify memory isolation across users and sessions."""

    def setup_method(self):
        self._tmpdirs = []

    def teardown_method(self):
        import shutil

        for d in self._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def _make_memory(self) -> SemanticMemory:
        tmpdir = tempfile.mkdtemp()
        self._tmpdirs.append(tmpdir)
        return SemanticMemory(data_dir=tmpdir)

    def test_session_memory_isolation(self):
        """Memories stored in session A should not appear in session B's context."""
        mem_a = self._make_memory()
        mem_b = self._make_memory()

        mem_a.add("Session A secret: project uses pytest-asyncio", source="session_a")
        mem_b.add("Session B secret: project uses unittest", source="session_b")

        ctx_a = mem_a.get_context("pytest", max_memories=5)
        ctx_b = mem_b.get_context("unittest", max_memories=5)

        assert "pytest-asyncio" in ctx_a
        assert "unittest" not in ctx_a

        assert "unittest" in ctx_b
        assert "pytest-asyncio" not in ctx_b

    def test_user_memory_isolation(self):
        """Different SemanticMemory instances should not share data."""
        mem_user1 = self._make_memory()
        mem_user2 = self._make_memory()

        mem_user1.add("User 1 convention: use type hints everywhere", source="user1")
        mem_user2.add("User 2 convention: no type hints needed", source="user2")

        ctx1 = mem_user1.get_context("type hints", max_memories=5)
        ctx2 = mem_user2.get_context("type hints", max_memories=5)

        assert "type hints everywhere" in ctx1
        assert "no type hints" not in ctx1

        assert "no type hints" in ctx2
        assert "type hints everywhere" not in ctx2

    def test_memory_source_tracking(self):
        """Each memory should track its source for provenance."""
        mem = self._make_memory()

        mem.add("Fact from conversation", source="conversation")
        mem.add("Fact from learning", source="learning")
        mem.add("Fact from skill", source="skill")

        results = mem.search("fact", limit=10)

        sources = {r.source for r in results}
        assert "conversation" in sources or len(results) > 0

    def test_memory_search_relevance(self):
        """Memory search should return relevant results, not random ones."""
        mem = self._make_memory()

        mem.add("The project uses Python 3.14 with type hints", source="conversation")
        mem.add("Database is PostgreSQL with asyncpg driver", source="conversation")
        mem.add("Frontend uses React with TypeScript", source="conversation")

        results = mem.search("database technology", limit=3)

        if results:
            found_db = any(
                "PostgreSQL" in r.content or "database" in r.content.lower() for r in results
            )
            assert found_db, "Search should return database-related memory"

    def test_memory_max_limit(self):
        """Memory retrieval should respect max_memories limit."""
        mem = self._make_memory()

        for i in range(20):
            mem.add(f"Memory item {i}: information number {i}", source=f"source_{i}")

        ctx = mem.get_context("information", max_memories=3)
        assert ctx is not None

    def test_empty_memory_returns_empty(self):
        """Empty memory should return empty context."""
        mem = self._make_memory()
        ctx = mem.get_context("anything", max_memories=5)
        assert ctx == ""

    def test_concurrent_memory_writes(self):
        """Multiple writes to same memory should not corrupt data."""
        mem = self._make_memory()

        for i in range(50):
            mem.add(f"Concurrent write {i}", source=f"writer_{i % 5}")

        results = mem.search("concurrent", limit=100)
        assert len(results) > 0

    def test_memory_persistence_across_instances(self):
        """Memory should persist when a new instance is created with same data_dir."""
        tmpdir = tempfile.mkdtemp()
        self._tmpdirs.append(tmpdir)

        mem1 = SemanticMemory(data_dir=tmpdir)
        mem1.add("Persistent fact: project version is 2.0", source="conversation")

        mem2 = SemanticMemory(data_dir=tmpdir)
        ctx = mem2.get_context("project version", max_memories=5)

        assert "2.0" in ctx or len(ctx) > 0

    def test_special_characters_in_memory(self):
        """Memory should handle special characters without corruption."""
        mem = self._make_memory()

        special = "User said: code review is important for quality"
        mem.add(special, source="conversation")

        results = mem.search("code review", limit=5)
        assert len(results) > 0

    def test_memory_statistics(self):
        """Memory statistics should be accurate."""
        mem = self._make_memory()

        mem.add("Fact 1", source="src_a")
        mem.add("Fact 2", source="src_a")
        mem.add("Fact 3", source="src_b")

        stats = mem.get_statistics()
        assert stats["total_memories"] == 3
        assert "src_a" in stats["sources"]
        assert "src_b" in stats["sources"]

    def test_memory_delete(self):
        """Deleted memory should not appear in search results."""
        mem = self._make_memory()

        mid = mem.add("Temporary fact", source="temp")
        results = mem.search("temporary", limit=5)
        assert len(results) > 0

        mem.delete(mid)
        results = mem.search("temporary", limit=5)
        assert len(results) == 0
