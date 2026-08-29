"""Memory system for Bahram Agent."""

from bahram.memory.base import BaseMemory
from bahram.memory.conversation import ConversationMemory
from bahram.memory.episodic import EpisodicMemory
from bahram.memory.semantic import SemanticMemory

__all__ = ["BaseMemory", "ConversationMemory", "EpisodicMemory", "SemanticMemory"]


async def init_memory(config: "Config") -> None:
    """Initialize memory systems."""
    # Memory initialization happens lazily when needed
    pass
