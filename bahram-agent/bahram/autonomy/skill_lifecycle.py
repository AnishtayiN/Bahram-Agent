from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from bahram.autonomy.learning import LearningEngine, SkillCandidate, Lesson

logger = logging.getLogger(__name__)


class LLMProviderForSkills(Protocol):
    async def complete(
        self, messages: list[Any], tools: list[dict[str, Any]] | None = None, **kwargs: Any
    ) -> Any: ...


class SkillLifecycle:
    def __init__(self, learning_engine: LearningEngine) -> None:
        self._learning = learning_engine

    async def generate_from_lessons(
        self,
        lesson_ids: list[str],
        task_description: str = "",
    ) -> SkillCandidate | None:
        skill = await self._learning.generate_skill(lesson_ids)
        if not skill:
            return None

        skill.status = "candidate"
        skill.confidence = 0.3
        self._learning._save()
        logger.info(f"Generated skill candidate: {skill.id} — {skill.name}")
        return skill

    async def validate(self, skill_id: str) -> str:
        status = await self._learning.validate_skill(skill_id)
        if status == "trusted":
            logger.info(f"Skill {skill_id} promoted to trusted")
        elif status == "rejected":
            logger.info(f"Skill {skill_id} rejected")
        return status

    async def record_usage(self, skill_id: str, success: bool) -> None:
        self._learning.record_skill_usage(skill_id, success)
        await self.validate(skill_id)

    def get_trusted_skills(self) -> list[SkillCandidate]:
        return [s for s in self._learning.get_skills() if s.status == "trusted"]

    def get_candidates(self) -> list[SkillCandidate]:
        return [s for s in self._learning.get_skills() if s.status == "candidate"]

    def get_skill(self, skill_id: str) -> SkillCandidate | None:
        return self._learning.get_skill(skill_id)

    def get_stats(self) -> dict[str, Any]:
        return self._learning.get_stats()
