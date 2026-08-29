"""Tests for memory modules."""
import pytest
from bahram.memory.semantic import SemanticMemory
from bahram.memory.providers import MemoryProviderManager

class TestSemanticMemory:
    def test_memory_creation(self, tmp_path):
        mem = SemanticMemory(data_dir=str(tmp_path))
        assert mem is not None

    def test_add_memory(self, tmp_path):
        mem = SemanticMemory(data_dir=str(tmp_path))
        mem_id = mem.add("Test memory content")
        assert mem_id is not None

    def test_search_memory(self, tmp_path):
        mem = SemanticMemory(data_dir=str(tmp_path))
        mem.add("Python is a programming language")
        results = mem.search("Python")
        assert len(results) > 0

class TestMemoryProviderManager:
    def test_provider_manager(self, tmp_path):
        manager = MemoryProviderManager(data_dir=str(tmp_path))
        assert manager is not None

    def test_get_local_provider(self, tmp_path):
        manager = MemoryProviderManager(data_dir=str(tmp_path))
        provider = manager.get_provider("local")
        assert provider is not None
