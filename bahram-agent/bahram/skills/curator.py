"""
Curator.

Public objects: ``CurationAction``, ``Curator``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CurationAction:
    """
    Curation action.

    Attributes:
        action (str): action string.
        skill_name (str): skill name string.
        reason (str): reason string.
        details (dict): mapping of details.
        timestamp (str): timestamp string.
    """

    action: str
    skill_name: str
    reason: str
    details: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class Curator:
    """
    Curator.
    """

    def __init__(self, skills_dir: str = "skills") -> None:
        """
        Initialise a Curator instance.

        Args:
            skills_dir (str): skills dir string. Defaults to ``'skills'``.
        """
        self.skills_dir = Path(skills_dir)
        self._actions: list[CurationAction] = []
        self._stats: dict[str, int] = {
            "suggestions": 0,
            "merges": 0,
            "splits": 0,
            "archives": 0,
            "deletions": 0,
        }

    def analyze_skills(self) -> list[CurationAction]:
        """
        Analyze skills.

        Returns:
            list[CurationAction]: a sequence of CurationAction entries (empty when there is nothing
                to report).
        """
        actions = []

        skills = self._load_all_skills()
        overlaps = self._find_overlapping(skills)
        for overlap in overlaps:
            actions.append(
                CurationAction(
                    action="merge",
                    skill_name=overlap["names"],
                    reason=overlap["reason"],
                )
            )

        unused = self._find_unused_skills(skills)
        for skill in unused:
            actions.append(
                CurationAction(
                    action="archive",
                    skill_name=skill,
                    reason="Skill has not been used in 30+ days",
                )
            )

        large = self._find_large_skills(skills)
        for skill in large:
            actions.append(
                CurationAction(
                    action="split",
                    skill_name=skill["name"],
                    reason=f"Skill is {skill['size']} chars, consider splitting",
                )
            )

        self._actions.extend(actions)
        return actions

    def _load_all_skills(self) -> list[dict]:
        skills = []
        if self.skills_dir.exists():
            for skill_file in self.skills_dir.rglob("SKILL.md"):
                try:
                    content = skill_file.read_text(encoding="utf-8")
                    skills.append(
                        {
                            "path": str(skill_file),
                            "name": skill_file.parent.name,
                            "content": content,
                            "size": len(content),
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to load {skill_file}: {e}")
        return skills

    def _find_overlapping(self, skills: list[dict]) -> list[dict]:
        overlaps = []
        for i, s1 in enumerate(skills):
            for s2 in skills[i + 1 :]:
                similarity = self._calculate_similarity(s1["content"], s2["content"])
                if similarity > 0.7:
                    overlaps.append(
                        {
                            "names": f"{s1['name']}, {s2['name']}",
                            "reason": f"Content similarity: {similarity:.0%}",
                        }
                    )
        return overlaps

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)

    def _find_unused_skills(self, skills: list[dict]) -> list[str]:

        return []

    def _find_large_skills(self, skills: list[dict]) -> list[dict]:
        return [s for s in skills if s["size"] > 10000]

    def get_stats(self) -> dict:
        """
        Return the stats.

        Returns:
            dict: a mapping of str, Any.
        """
        return self._stats.copy()

    def get_pending_actions(self) -> list[CurationAction]:
        """
        Return the pending actions.

        Returns:
            list[CurationAction]: a sequence of CurationAction entries (empty when there is nothing
                to report).
        """
        return self._actions.copy()
