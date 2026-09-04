"""
Learning.

Public objects: ``Lesson``, ``SkillCandidate``, ``LearningEngine``.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Lesson:
    """
    Lesson.

    Attributes:
        id (str): id string.
        content (str): text content to process.
        scope (str): scope string.
        source_run (str): source run string.
        confidence (float): numeric value for confidence.
        usage_count (int): numeric value for usage count.
        success_count (int): numeric value for success count.
        failure_count (int): numeric value for failure count.
        created_at (float): numeric value for created at.
        updated_at (float): numeric value for updated at.
        metadata (dict[str, Any]): mapping of metadata.
    """

    id: str
    content: str
    scope: str
    source_run: str
    confidence: float = 0.5
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """
        Success rate.

        Returns:
            float: the computed numeric value.
        """
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """
        Serialise the object to a JSON-serialisable dictionary.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {
            "id": self.id,
            "content": self.content,
            "scope": self.scope,
            "source_run": self.source_run,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


@dataclass
class SkillCandidate:
    """
    Skill candidate.

    Attributes:
        id (str): id string.
        name (str): name of the object.
        description (str): human readable description.
        instructions (str): instructions string.
        triggers (list[str]): collection of triggers.
        prerequisites (list[str]): collection of prerequisites.
        required_capabilities (list[str]): collection of required capabilities.
        version (str): version string.
        confidence (float): numeric value for confidence.
        usage_count (int): numeric value for usage count.
        success_count (int): numeric value for success count.
        failure_count (int): numeric value for failure count.
        status (str): status string.
        created_at (float): numeric value for created at.
        updated_at (float): numeric value for updated at.
        source_lessons (list[str]): collection of source lessons.
        provenance (dict[str, Any]): mapping of provenance.
    """

    id: str
    name: str
    description: str
    instructions: str
    triggers: list[str]
    prerequisites: list[str] = field(default_factory=list)
    required_capabilities: list[str] = field(default_factory=list)
    version: str = "0.1.0"
    confidence: float = 0.3
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    status: str = "candidate"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    source_lessons: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """
        Success rate.

        Returns:
            float: the computed numeric value.
        """
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """
        Serialise the object to a JSON-serialisable dictionary.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "triggers": self.triggers,
            "prerequisites": self.prerequisites,
            "required_capabilities": self.required_capabilities,
            "version": self.version,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source_lessons": self.source_lessons,
            "provenance": self.provenance,
        }


class LearningEngine:
    """
    Learning engine.
    """

    def __init__(self, data_dir: str | None = "data/learning") -> None:
        """
        Initialise a LearningEngine instance.

        Args:
            data_dir (str): directory that holds the on-disk state, or ``None`` for ephemeral
                in-memory operation. Defaults to ``'data/learning'``.
        """
        self._data_dir = Path(data_dir) if data_dir else None
        if self._data_dir is not None:
            self._data_dir.mkdir(parents=True, exist_ok=True)
        self._lessons: dict[str, Lesson] = {}
        self._skills: dict[str, SkillCandidate] = {}
        self._load()

    def _load(self) -> None:
        if self._data_dir is None:
            return
        lessons_file = self._data_dir / "lessons.json"
        skills_file = self._data_dir / "skill_candidates.json"

        if lessons_file.exists():
            try:
                with open(lessons_file) as f:
                    data = json.load(f)
                for item in data:
                    lesson = Lesson(**item)
                    self._lessons[lesson.id] = lesson
            except Exception as e:
                logger.warning(f"Failed to load lessons: {e}")

        if skills_file.exists():
            try:
                with open(skills_file) as f:
                    data = json.load(f)
                for item in data:
                    skill = SkillCandidate(**item)
                    self._skills[skill.id] = skill
            except Exception as e:
                logger.warning(f"Failed to load skill candidates: {e}")

    def _save(self) -> None:
        if self._data_dir is None:
            return
        try:
            lessons_file = self._data_dir / "lessons.json"
            with open(lessons_file, "w") as f:
                json.dump([lesson.to_dict() for lesson in self._lessons.values()], f, indent=2)

            skills_file = self._data_dir / "skill_candidates.json"
            with open(skills_file, "w") as f:
                json.dump([s.to_dict() for s in self._skills.values()], f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save learning data: {e}")

    async def analyze_outcome(
        self,
        run_id: str,
        goal: str,
        trajectory_steps: list[dict[str, Any]],
        tool_results: list[dict[str, Any]],
        success: bool,
    ) -> dict[str, Any]:
        """
        Analyze outcome.

        Args:
            run_id (str): run identifier.
            goal (str): goal string.
            trajectory_steps (list[dict[str, Any]]): collection of trajectory steps.
            tool_results (list[dict[str, Any]]): collection of tool results.
            success (bool): when ``True``, enable success.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        analysis = {
            "run_id": run_id,
            "goal": goal,
            "success": success,
            "total_steps": len(trajectory_steps),
            "total_tool_calls": len(tool_results),
            "tools_used": list({r.get("tool", "") for r in tool_results}),
            "successful_tools": [
                r.get("tool", "") for r in tool_results if r.get("success", False)
            ],
            "failed_tools": [r.get("tool", "") for r in tool_results if not r.get("success", True)],
            "lessons_extracted": [],
        }

        if success:
            if len(tool_results) > 0:
                success_rate = sum(1 for r in tool_results if r.get("success", False)) / len(
                    tool_results
                )
                if success_rate < 0.8:
                    lesson = await self._extract_lesson(
                        run_id, goal, tool_results, "Tool success rate was low"
                    )
                    if lesson:
                        analysis["lessons_extracted"].append(lesson.id)

            if len(trajectory_steps) > 5:
                lesson = await self._extract_lesson(
                    run_id, goal, tool_results, "Task required many iterations"
                )
                if lesson:
                    analysis["lessons_extracted"].append(lesson.id)
        else:
            failed_tools = [r for r in tool_results if not r.get("success", True)]
            for ft in failed_tools[:3]:
                lesson = await self._extract_lesson(
                    run_id,
                    goal,
                    tool_results,
                    f"Tool '{ft.get('tool', '')}' failed: {ft.get('error', 'unknown')}",
                )
                if lesson:
                    analysis["lessons_extracted"].append(lesson.id)

        return analysis

    async def _extract_lesson(
        self,
        run_id: str,
        goal: str,
        tool_results: list[dict[str, Any]],
        observation: str,
    ) -> Lesson | None:
        existing = [
            lesson
            for lesson in self._lessons.values()
            if lesson.source_run == run_id or observation.lower() in lesson.content.lower()
        ]
        if existing:
            return None

        lesson = Lesson(
            id=f"lesson_{uuid.uuid4().hex[:8]}",
            content=observation,
            scope=self._infer_scope(goal),
            source_run=run_id,
            confidence=0.4,
            metadata={"goal": goal, "tools_used": list({r.get("tool", "") for r in tool_results})},
        )
        self._lessons[lesson.id] = lesson
        self._save()
        logger.info(f"Extracted lesson: {lesson.id} — {observation[:100]}")
        return lesson

    def _infer_scope(self, goal: str) -> str:
        goal_lower = goal.lower()
        if any(w in goal_lower for w in ("test", "pytest", "unittest")):
            return "testing"
        if any(w in goal_lower for w in ("deploy", "docker", "kubernetes")):
            return "deployment"
        if any(w in goal_lower for w in ("fix", "bug", "error")):
            return "debugging"
        if any(w in goal_lower for w in ("refactor", "clean", "restructure")):
            return "refactoring"
        return "general"

    async def generate_skill(self, lesson_ids: list[str]) -> SkillCandidate | None:
        """
        Generate skill.

        Args:
            lesson_ids (list[str]): collection of lesson ids.

        Returns:
            SkillCandidate | None: the resulting object, or ``None`` when it is not available.

        Note:
            Coroutine - must be awaited.
        """
        lessons = [self._lessons[lid] for lid in lesson_ids if lid in self._lessons]
        if not lessons:
            return None

        combined_content = " ".join(lesson.content for lesson in lessons)

        skill = SkillCandidate(
            id=f"skill_{uuid.uuid4().hex[:8]}",
            name=self._generate_skill_name(combined_content),
            description=f"Auto-generated skill from {len(lessons)} lesson(s)",
            instructions=self._generate_instructions(lessons),
            triggers=self._generate_triggers(combined_content),
            prerequisites=[],
            required_capabilities=[],
            source_lessons=[lesson.id for lesson in lessons],
            provenance={"generated_from": "learning_loop", "lesson_count": len(lessons)},
        )

        self._skills[skill.id] = skill
        self._save()
        logger.info(f"Generated skill candidate: {skill.id} — {skill.name}")
        return skill

    def _generate_skill_name(self, content: str) -> str:
        words = content.lower().split()
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "was",
            "were",
            "are",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "shall",
            "can",
            "need",
            "dare",
            "ought",
            "used",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "out",
            "off",
            "over",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "when",
            "where",
            "why",
            "how",
            "all",
            "both",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "just",
        }
        meaningful = [w for w in words if w not in stop_words and len(w) > 2][:5]
        return "_".join(meaningful) if meaningful else "auto_skill"

    def _generate_instructions(self, lessons: list[Lesson]) -> str:
        instructions = "Lessons to follow:\n"
        for i, lesson in enumerate(lessons, 1):
            instructions += f"{i}. {lesson.content}\n"
        return instructions

    def _generate_triggers(self, content: str) -> list[str]:
        words = content.lower().split()
        stop_words = {"the", "a", "an", "is", "was", "for", "in", "on", "to", "of"}
        meaningful = [w for w in words if w not in stop_words and len(w) > 3][:3]
        return meaningful if meaningful else ["auto"]

    async def validate_skill(self, skill_id: str) -> str:
        """
        Validate skill.

        Args:
            skill_id (str): skill id string.

        Returns:
            str: the rendered string.

        Note:
            Coroutine - must be awaited.
        """
        skill = self._skills.get(skill_id)
        if not skill:
            return "not_found"

        if skill.usage_count < 3:
            skill.confidence = min(0.5, skill.confidence + 0.1)
            skill.status = "candidate"
        elif skill.success_rate >= 0.8:
            skill.confidence = min(1.0, skill.confidence + 0.2)
            skill.status = "trusted" if skill.confidence >= 0.7 else "tested"
        elif skill.success_rate < 0.5:
            skill.confidence = max(0.0, skill.confidence - 0.3)
            skill.status = "rejected" if skill.confidence < 0.2 else "candidate"
        else:
            skill.confidence = min(1.0, skill.confidence + 0.05)
            skill.status = "tested"

        skill.updated_at = time.time()
        self._save()
        return skill.status

    def record_skill_usage(self, skill_id: str, success: bool) -> None:
        """
        Record skill usage.

        Args:
            skill_id (str): skill id string.
            success (bool): when ``True``, enable success.
        """
        skill = self._skills.get(skill_id)
        if skill:
            skill.usage_count += 1
            if success:
                skill.success_count += 1
            else:
                skill.failure_count += 1
            skill.updated_at = time.time()
            self._save()

    def get_relevant_skills(self, task: str, limit: int = 3) -> list[SkillCandidate]:
        """
        Return the relevant skills.

        Args:
            task (str): task string.
            limit (int): maximum number of items to return. Defaults to ``3``.

        Returns:
            list[SkillCandidate]: a sequence of SkillCandidate entries (empty when there is nothing
                to report).
        """
        task_lower = task.lower()
        scored = []
        for skill in self._skills.values():
            if skill.status == "rejected":
                continue
            trigger_match = sum(1 for t in skill.triggers if t.lower() in task_lower)
            if trigger_match > 0:
                score = trigger_match * skill.confidence
                scored.append((score, skill))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:limit]]

    def get_relevant_lessons(self, task: str, limit: int = 5) -> list[Lesson]:
        """
        Return the relevant lessons.

        Args:
            task (str): task string.
            limit (int): maximum number of items to return. Defaults to ``5``.

        Returns:
            list[Lesson]: a sequence of Lesson entries (empty when there is nothing to report).
        """
        task_lower = task.lower()
        scored = []
        for lesson in self._lessons.values():
            relevance = sum(1 for w in lesson.content.lower().split() if w in task_lower)
            if relevance > 0:
                score = relevance * lesson.confidence
                scored.append((score, lesson))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [lesson for _, lesson in scored[:limit]]

    def get_lessons(self) -> list[Lesson]:
        """
        Return the lessons.

        Returns:
            list[Lesson]: a sequence of Lesson entries (empty when there is nothing to report).
        """
        return list(self._lessons.values())

    def get_skills(self) -> list[SkillCandidate]:
        """
        Return the skills.

        Returns:
            list[SkillCandidate]: a sequence of SkillCandidate entries (empty when there is nothing
                to report).
        """
        return list(self._skills.values())

    def get_skill(self, skill_id: str) -> SkillCandidate | None:
        """
        Return the skill.

        Args:
            skill_id (str): skill id string.

        Returns:
            SkillCandidate | None: the resulting object, or ``None`` when it is not available.
        """
        return self._skills.get(skill_id)

    def get_stats(self) -> dict[str, Any]:
        """
        Return the stats.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        lessons = list(self._lessons.values())
        skills = list(self._skills.values())
        return {
            "total_lessons": len(lessons),
            "total_skills": len(skills),
            "trusted_skills": sum(1 for s in skills if s.status == "trusted"),
            "candidate_skills": sum(1 for s in skills if s.status == "candidate"),
            "rejected_skills": sum(1 for s in skills if s.status == "rejected"),
            "avg_lesson_confidence": (
                sum(lesson.confidence for lesson in lessons) / len(lessons) if lessons else 0
            ),
            "avg_skill_confidence": (
                sum(s.confidence for s in skills) / len(skills) if skills else 0
            ),
        }
