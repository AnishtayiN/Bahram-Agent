"""Skills system for Bahram Agent."""

from bahram.skills.base import BaseSkill
from bahram.skills.manager import SkillManager

__all__ = ["BaseSkill", "SkillManager"]


async def init_skills(engine: "AgentEngine", config: "Config") -> None:
    """Initialize skills system."""
    manager = SkillManager(config.skills)
    await manager.load_skills()
