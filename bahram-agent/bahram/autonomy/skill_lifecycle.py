"""
Skill lifecycle.

Public objects: ``LLMProviderForSkills``, ``SkillLifecycle``.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from bahram.autonomy.learning import LearningEngine, SkillCandidate

logger = logging.getLogger(__name__)


class LLMProviderForSkills(Protocol):
    """
    LLM provider for skills.
    """

    async def complete(
        self, messages: list[Any], tools: list[dict[str, Any]] | None = None, **kwargs: Any
    ) -> Any:
        """Send a chat completion request and return the raw provider response.

        Args:
            messages (list[Any]): conversation history to send.
            tools (list[dict[str, Any]] | None): OpenAI-style tool schemas.
                Defaults to ``None``.
            **kwargs (Any): provider specific overrides.

        Returns:
            Any: the provider response object (``AgentResponse`` for the real
                engine implementations).

        Note:
            Coroutine - must be awaited.
        """
        ...


class SkillLifecycle:
    """
    Skill lifecycle.
    """

    def __init__(self, learning_engine: LearningEngine) -> None:
        """
        Initialise a SkillLifecycle instance.

        Args:
            learning_engine (LearningEngine): learning engine.
        """
        self._learning = learning_engine

    async def generate_from_lessons(
        self,
        lesson_ids: list[str],
        task_description: str = "",
    ) -> SkillCandidate | None:
        """
        Generate from lessons.

        Args:
            lesson_ids (list[str]): collection of lesson ids.
            task_description (str): task description string. Defaults to ``''``.

        Returns:
            SkillCandidate | None: the resulting object, or ``None`` when it is not available.

        Note:
            Coroutine - must be awaited.
        """
        skill = await self._learning.generate_skill(lesson_ids)
        if not skill:
            return None

        skill.status = "candidate"
        skill.confidence = 0.3
        self._learning._save()
        logger.info(f"Generated skill candidate: {skill.id} — {skill.name}")
        return skill

    async def validate(self, skill_id: str) -> str:
        """
        Validate.

        Args:
            skill_id (str): skill id string.

        Returns:
            str: the rendered string.

        Note:
            Coroutine - must be awaited.
        """
        status = await self._learning.validate_skill(skill_id)
        if status == "trusted":
            logger.info(f"Skill {skill_id} promoted to trusted")
        elif status == "rejected":
            logger.info(f"Skill {skill_id} rejected")
        return status

    async def record_usage(self, skill_id: str, success: bool) -> None:
        """
        Record usage.

        Args:
            skill_id (str): skill id string.
            success (bool): when ``True``, enable success.

        Note:
            Coroutine - must be awaited.
        """
        self._learning.record_skill_usage(skill_id, success)
        await self.validate(skill_id)

    def get_trusted_skills(self) -> list[SkillCandidate]:
        """
        Return the trusted skills.

        Returns:
            list[SkillCandidate]: a sequence of SkillCandidate entries (empty when there is nothing
                to report).
        """
        return [s for s in self._learning.get_skills() if s.status == "trusted"]

    def get_candidates(self) -> list[SkillCandidate]:
        """
        Return the candidates.

        Returns:
            list[SkillCandidate]: a sequence of SkillCandidate entries (empty when there is nothing
                to report).
        """
        return [s for s in self._learning.get_skills() if s.status == "candidate"]

    def get_skill(self, skill_id: str) -> SkillCandidate | None:
        """
        Return the skill.

        Args:
            skill_id (str): skill id string.

        Returns:
            SkillCandidate | None: the resulting object, or ``None`` when it is not available.
        """
        return self._learning.get_skill(skill_id)

    def get_stats(self) -> dict[str, Any]:
        """
        Return the stats.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return self._learning.get_stats()
