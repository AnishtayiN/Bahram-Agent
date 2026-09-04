from __future__ import annotations

from bahram.memory.semantic import SemanticMemory


class TestSemanticMemory:
    def test_init(self, tmp_path):
        mem = SemanticMemory(data_dir=str(tmp_path))
        assert mem is not None

    def test_add_memory(self, tmp_path):
        mem = SemanticMemory(data_dir=str(tmp_path))
        mid = mem.add("Python is a programming language", source="test")
        assert mid is not None
        assert len(mid) > 0

    def test_search_exact(self, tmp_path):
        mem = SemanticMemory(data_dir=str(tmp_path))
        mem.add("Python is a programming language", source="test")
        results = mem.search("Python")
        assert len(results) > 0
        assert results[0].score > 0

    def test_search_partial(self, tmp_path):
        mem = SemanticMemory(data_dir=str(tmp_path))
        mem.add("The quick brown fox jumps over the lazy dog", source="test")
        results = mem.search("quick")
        assert len(results) > 0

    def test_search_empty(self, tmp_path):
        mem = SemanticMemory(data_dir=str(tmp_path))
        results = mem.search("xyznonexistent")
        assert len(results) == 0

    def test_get_context(self, tmp_path):
        mem = SemanticMemory(data_dir=str(tmp_path))
        mem.add("Important fact about Python", source="docs")
        context = mem.get_context("Python")
        assert "Python" in context

    def test_get_statistics(self, tmp_path):
        mem = SemanticMemory(data_dir=str(tmp_path))
        mem.add("Fact 1", source="a")
        mem.add("Fact 2", source="b")
        stats = mem.get_statistics()
        assert stats["total_memories"] == 2

    def test_delete_memory(self, tmp_path):
        mem = SemanticMemory(data_dir=str(tmp_path))
        mid = mem.add("Delete me")
        assert mem.delete(mid) is True
        assert mem.get(mid) is None

    def test_persistence(self, tmp_path):
        mem1 = SemanticMemory(data_dir=str(tmp_path))
        mem1.add("Persistent fact", source="test")
        mem2 = SemanticMemory(data_dir=str(tmp_path))
        results = mem2.search("Persistent")
        assert len(results) > 0

    def test_search_ranking(self, tmp_path):
        mem = SemanticMemory(data_dir=str(tmp_path))
        mem.add("Python programming language", source="a")
        mem.add("Java programming language", source="b")
        results = mem.search("Python")
        assert results[0].content == "Python programming language"
