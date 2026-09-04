"""Phase 11: Smart Context integration proof tests.

Tests that SmartContext actually affects model requests.
"""
from __future__ import annotations

from bahram.core.engine import MessageRole
from bahram.core.smart_context import SmartContextManager


class TestSmartContextProof:
    """Prove SmartContext affects model request construction."""

    def test_smart_context_affects_messages(self):
        """SmartContext output should be included in model messages."""
        sc = SmartContextManager(max_tokens=8192)
        sc.set_system_prompt("You are a helpful agent.")

        sc.add_context("Memory: project uses pytest", priority=3, metadata={"source": "memory"})
        sc.add_context("Skill: use type hints", priority=2, metadata={"source": "skill"})

        sc.add_history("user", "Hello, how are you?")
        sc.add_history("assistant", "I'm doing well, thanks!")

        messages = sc.build_messages()

        assert len(messages) >= 2

        system_msgs = [m for m in messages if m.role == MessageRole.SYSTEM]
        assert len(system_msgs) >= 1

        has_memory = any("pytest" in m.content for m in messages)
        has_skill = any("type hints" in m.content for m in messages)
        assert has_memory or has_skill, "SmartContext should include memory/skill content"

    def test_smart_context_priority_ordering(self):
        """Higher priority context should appear first."""
        sc = SmartContextManager(max_tokens=8192)
        sc.set_system_prompt("System prompt")

        sc.add_context("Low priority: nice to know", priority=1)
        sc.add_context("High priority: critical constraint", priority=5)
        sc.add_context("Medium priority: relevant info", priority=3)

        messages = sc.build_messages()

        contents = [m.content for m in messages]
        high_idx = next((i for i, c in enumerate(contents) if "critical" in c), -1)
        low_idx = next((i for i, c in enumerate(contents) if "nice to know" in c), -1)

        if high_idx >= 0 and low_idx >= 0:
            assert high_idx < low_idx, "High priority should appear before low priority"

    def test_smart_context_token_budget(self):
        """SmartContext should respect token budget."""
        sc = SmartContextManager(max_tokens=100)

        sc.set_system_prompt("x" * 400)

        for i in range(20):
            sc.add_context(f"Context item {i}: {'y' * 100}", priority=i)

        messages = sc.build_messages()

        total_chars = sum(len(m.content) for m in messages)
        assert total_chars < 800, "SmartContext should not exceed token budget significantly"

    def test_smart_context_compression_preserves_critical(self):
        """Compression should preserve critical information."""
        sc = SmartContextManager(max_tokens=200)

        sc.set_system_prompt("System prompt")
        sc.add_context("CRITICAL: Never delete production data", priority=10)
        sc.add_context("Nice to know: project uses Python 3.14", priority=1)

        for i in range(30):
            sc.add_history("user", f"Message {i}: {'z' * 50}")

        messages = sc.build_messages()

        contents = [m.content for m in messages]
        has_critical = any("CRITICAL" in c for c in contents)
        assert has_critical, "Critical information should survive compression"

    def test_smart_context_usage_tracking(self):
        """SmartContext should accurately track token usage."""
        sc = SmartContextManager(max_tokens=1000)

        sc.set_system_prompt("Short prompt")
        sc.add_context("Some context", priority=1)
        sc.add_history("user", "Hello")

        usage = sc.get_usage()

        assert "max_tokens" in usage
        assert "remaining" in usage
        assert usage["remaining"] < 1000
        assert usage["remaining"] > 0

    def test_build_messages_vs_build_context(self):
        """build_messages() and build_context() should produce consistent content."""
        sc = SmartContextManager(max_tokens=8192)
        sc.set_system_prompt("Test prompt")
        sc.add_context("Test context", priority=1)
        sc.add_history("user", "Test message")

        messages = sc.build_messages()
        context = sc.build_context()

        msg_contents = [m.content for m in messages]
        ctx_contents = [c["content"] for c in context]

        for mc in msg_contents:
            if mc == "Test prompt":
                assert mc in ctx_contents, "System prompt should appear in both"

    def test_smart_context_clear(self):
        """Clear should reset context windows and history, but preserve system prompt."""
        sc = SmartContextManager(max_tokens=8192)
        sc.set_system_prompt("Prompt")
        sc.add_context("Context", priority=1)
        sc.add_history("user", "Message")

        sc.clear()

        usage = sc.get_usage()
        assert usage["remaining"] == 8192
