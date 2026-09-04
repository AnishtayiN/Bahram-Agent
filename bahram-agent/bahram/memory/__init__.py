from __future__ import annotations

from bahram.memory.base import BaseMemory
from bahram.memory.conversation import ConversationMemory
from bahram.memory.episodic import EpisodicMemory
from bahram.memory.semantic import SemanticMemory

__all__ = ["BaseMemory", "ConversationMemory", "EpisodicMemory", "SemanticMemory"]

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bahram.core.config import Config


async def init_memory(config: "Config") -> None:

    pass
