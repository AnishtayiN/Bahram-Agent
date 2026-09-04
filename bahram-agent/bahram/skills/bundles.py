"""
Bundles.

Public objects: ``SkillBundle``, ``SkillBundles``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SkillBundle:
    """
    Skill bundle.

    Attributes:
        name (str): name of the object.
        description (str): human readable description.
        skills (list[str]): collection of skills.
        enabled (bool): when ``True`` the object is active.
    """

    name: str
    description: str
    skills: list[str] = field(default_factory=list)
    enabled: bool = True


class SkillBundles:
    """
    Skill bundles.
    """

    def __init__(self, data_dir: str = "data/skills") -> None:
        """
        Initialise a SkillBundles instance.

        Args:
            data_dir (str): directory that holds the on-disk state. Defaults to ``'data/skills'``.
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._bundles: dict[str, SkillBundle] = {}
        self._load()

    def _load(self) -> None:
        bundles_file = self.data_dir / "bundles.json"
        if bundles_file.exists():
            try:
                with open(bundles_file) as f:
                    data = json.load(f)
                for bundle_data in data:
                    bundle = SkillBundle(**bundle_data)
                    self._bundles[bundle.name] = bundle
            except Exception as e:
                logger.warning(f"Failed to load bundles: {e}")

    def _save(self) -> None:
        bundles_file = self.data_dir / "bundles.json"
        data = [
            {
                "name": b.name,
                "description": b.description,
                "skills": b.skills,
                "enabled": b.enabled,
            }
            for b in self._bundles.values()
        ]
        with open(bundles_file, "w") as f:
            json.dump(data, f, indent=2)

    def create_bundle(self, name: str, description: str, skills: list[str] = None) -> SkillBundle:
        """
        Create bundle.

        Args:
            name (str): name of the object.
            description (str): human readable description.
            skills (list[str]): collection of skills. Defaults to ``None``.

        Returns:
            SkillBundle: the resulting SkillBundle.
        """
        bundle = SkillBundle(
            name=name,
            description=description,
            skills=skills or [],
        )
        self._bundles[name] = bundle
        self._save()
        return bundle

    def add_skill_to_bundle(self, bundle_name: str, skill_name: str) -> bool:
        """
        Add skill to bundle.

        Args:
            bundle_name (str): bundle name string.
            skill_name (str): skill name string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        bundle = self._bundles.get(bundle_name)
        if bundle and skill_name not in bundle.skills:
            bundle.skills.append(skill_name)
            self._save()
            return True
        return False

    def remove_skill_from_bundle(self, bundle_name: str, skill_name: str) -> bool:
        """
        Remove skill from bundle.

        Args:
            bundle_name (str): bundle name string.
            skill_name (str): skill name string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        bundle = self._bundles.get(bundle_name)
        if bundle and skill_name in bundle.skills:
            bundle.skills.remove(skill_name)
            self._save()
            return True
        return False

    def enable_bundle(self, name: str) -> bool:
        """
        Enable bundle.

        Args:
            name (str): name of the object.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        bundle = self._bundles.get(name)
        if bundle:
            bundle.enabled = True
            self._save()
            return True
        return False

    def disable_bundle(self, name: str) -> bool:
        """
        Disable bundle.

        Args:
            name (str): name of the object.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        bundle = self._bundles.get(name)
        if bundle:
            bundle.enabled = False
            self._save()
            return True
        return False

    def get_bundle(self, name: str) -> SkillBundle | None:
        """
        Return the bundle.

        Args:
            name (str): name of the object.

        Returns:
            SkillBundle | None: the resulting object, or ``None`` when it is not available.
        """
        return self._bundles.get(name)

    def get_enabled_skills(self) -> list[str]:
        """
        Return the enabled skills.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        skills = []
        for bundle in self._bundles.values():
            if bundle.enabled:
                skills.extend(bundle.skills)
        return list(set(skills))

    def list_bundles(self) -> list[dict]:
        """
        List bundles.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        return [
            {
                "name": b.name,
                "description": b.description,
                "skills": b.skills,
                "enabled": b.enabled,
            }
            for b in self._bundles.values()
        ]

    def delete_bundle(self, name: str) -> bool:
        """
        Delete bundle.

        Args:
            name (str): name of the object.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        if name in self._bundles:
            del self._bundles[name]
            self._save()
            return True
        return False
