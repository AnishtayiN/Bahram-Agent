from bahram.skills.base import BaseSkill
from bahram.skills.manager import SkillManager

__all__ = ["BaseSkill", "SkillManager"]

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bahram.core.config import Config
    from bahram.core.engine import AgentEngine


async def init_skills(engine: "AgentEngine", config: "Config") -> None:
    manager = SkillManager(config.skills)
    await manager.load_skills()
