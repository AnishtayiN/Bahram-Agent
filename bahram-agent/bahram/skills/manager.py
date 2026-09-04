"""
Manager.

Public objects: ``SkillManager``.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Any

from bahram.skills.base import BaseSkill

logger = logging.getLogger(__name__)


class SkillManager:
    """
    Skill manager.
    """

    def __init__(self, config: Any = None) -> None:
        """Initialise a SkillManager instance.

        Args:
            config (Any): configuration object with a ``directory`` attribute.
                Defaults to ``None``, which resolves the skills directory
                relative to the current working directory and then falls back
                to the one shipped beside the package - so ``bahram skills
                --list`` still works when the CLI is installed as a wheel and
                invoked from an unrelated directory.
        """
        self.config = config
        self.skills: dict[str, BaseSkill] = {}
        directory = getattr(config, "directory", "") if config is not None else ""
        self.skill_dir = self._resolve_dir(directory)

    @staticmethod
    def _resolve_dir(directory: str) -> Path:
        """Pick the skills directory: explicit, then CWD, then the package one."""
        if directory:
            return Path(directory)
        local = Path("skills")
        if local.exists():
            return local
        return Path(__file__).resolve().parents[2] / "skills"

    async def load_skills(self) -> None:
        """
        Load skills.

        Note:
            Coroutine - must be awaited.
        """
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
        # exec_module is synchronous - awaiting its None return raised
        # "object NoneType can't be used in 'await' expression", so not a
        # single skill was ever loaded.
        spec.loader.exec_module(module)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, BaseSkill) and attr is not BaseSkill:
                skill = attr()
                self.skills[skill.metadata.name] = skill
                logger.info(f"Loaded skill: {skill.metadata.name}")
                break

    def get_skill(self, name: str) -> BaseSkill | None:
        """
        Return the skill.

        Args:
            name (str): name of the object.

        Returns:
            BaseSkill | None: the resulting object, or ``None`` when it is not available.
        """
        return self.skills.get(name)

    def list_skills(self) -> list[str]:
        """
        List skills.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        return list(self.skills.keys())

    async def find_skill(self, task: str) -> BaseSkill | None:
        """
        Find skill.

        Args:
            task (str): task string.

        Returns:
            BaseSkill | None: the resulting object, or ``None`` when it is not available.

        Note:
            Coroutine - must be awaited.
        """
        for skill in self.skills.values():
            if await skill.can_handle(task):
                return skill
        return None

    async def execute_skill(self, name: str, context: dict[str, Any]) -> str:
        """
        Execute skill.

        Args:
            name (str): name of the object.
            context (dict[str, Any]): mapping of context.

        Returns:
            str: the rendered string.

        Note:
            Coroutine - must be awaited.
        """
        skill = self.get_skill(name)
        if skill is None:
            return f"Skill not found: {name}"

        try:
            return await skill.execute(context)
        except Exception as e:
            logger.error(f"Skill execution failed: {e}")
            return f"Skill execution failed: {e}"

    async def auto_execute(self, task: str, context: dict[str, Any]) -> str | None:
        """
        Auto execute.

        Args:
            task (str): task string.
            context (dict[str, Any]): mapping of context.

        Returns:
            str | None: the resulting object, or ``None`` when it is not available.

        Note:
            Coroutine - must be awaited.
        """
        skill = await self.find_skill(task)
        if skill:
            logger.info(f"Auto-executing skill: {skill.metadata.name}")
            return await skill.execute(context)
        return None
