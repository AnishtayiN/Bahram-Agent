from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Any, Optional

from bahram.skills.base import BaseSkill

logger = logging.getLogger(__name__)

class SkillManager:

    def __init__(self, config: Any) -> None:
        self.config = config
        self.skills: dict[str, BaseSkill] = {}
        self.skill_dir = Path(config.directory) if config.directory else Path("skills")

    async def load_skills(self) -> None:
        if not self.skill_dir.exists():
            logger.warning(f"Skills directory not found: {self.skill_dir}")
            return

        for skill_file in self.skill_dir.glob("*.py"):
            if skill_file.name.startswith("_"):
                continue

            try:
                await self._load_skill(skill_file)
            except Exception as e:
                logger.error(f"Failed to load skill {skill_file}: {e}")

        logger.info(f"Loaded {len(self.skills)} skills")

    async def _load_skill(self, skill_file: Path) -> None:
        module_name = skill_file.stem
        spec = importlib.util.spec_from_file_location(module_name, skill_file)

        if spec is None or spec.loader is None:
            return

        module = importlib.util.module_from_spec(spec)
        await spec.loader.exec_module(module)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseSkill)
                and attr is not BaseSkill
            ):
                skill = attr()
                self.skills[skill.metadata.name] = skill
                logger.info(f"Loaded skill: {skill.metadata.name}")
                break

    def get_skill(self, name: str) -> BaseSkill | None:
        return self.skills.get(name)

    def list_skills(self) -> list[str]:
        return list(self.skills.keys())

    async def find_skill(self, task: str) -> BaseSkill | None:
        for skill in self.skills.values():
            if await skill.can_handle(task):
                return skill
        return None

    async def execute_skill(self, name: str, context: dict[str, Any]) -> str:
        skill = self.get_skill(name)
        if skill is None:
            return f"Skill not found: {name}"

        try:
            return await skill.execute(context)
        except Exception as e:
            logger.error(f"Skill execution failed: {e}")
            return f"Skill execution failed: {e}"

    async def auto_execute(self, task: str, context: dict[str, Any]) -> str | None:
        skill = await self.find_skill(task)
        if skill:
            logger.info(f"Auto-executing skill: {skill.metadata.name}")
            return await skill.execute(context)
        return None
