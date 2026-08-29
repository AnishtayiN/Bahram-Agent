"""Skill bundles for Bahram Agent."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillBundle:
    """A bundle of related skills."""

    name: str
    description: str
    skills: list[str] = field(default_factory=list)
    enabled: bool = True


class SkillBundles:
    """Manage skill bundles."""

    def __init__(self, data_dir: str = "data/skills") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._bundles: dict[str, SkillBundle] = {}
        self._load()

    def _load(self) -> None:
        """Load bundles from disk."""
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
        """Save bundles to disk."""
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
        """Create a new bundle."""
        bundle = SkillBundle(
            name=name,
            description=description,
            skills=skills or [],
        )
        self._bundles[name] = bundle
        self._save()
        return bundle

    def add_skill_to_bundle(self, bundle_name: str, skill_name: str) -> bool:
        """Add a skill to a bundle."""
        bundle = self._bundles.get(bundle_name)
        if bundle and skill_name not in bundle.skills:
            bundle.skills.append(skill_name)
            self._save()
            return True
        return False

    def remove_skill_from_bundle(self, bundle_name: str, skill_name: str) -> bool:
        """Remove a skill from a bundle."""
        bundle = self._bundles.get(bundle_name)
        if bundle and skill_name in bundle.skills:
            bundle.skills.remove(skill_name)
            self._save()
            return True
        return False

    def enable_bundle(self, name: str) -> bool:
        """Enable a bundle."""
        bundle = self._bundles.get(name)
        if bundle:
            bundle.enabled = True
            self._save()
            return True
        return False

    def disable_bundle(self, name: str) -> bool:
        """Disable a bundle."""
        bundle = self._bundles.get(name)
        if bundle:
            bundle.enabled = False
            self._save()
            return True
        return False

    def get_bundle(self, name: str) -> Optional[SkillBundle]:
        """Get a bundle."""
        return self._bundles.get(name)

    def get_enabled_skills(self) -> list[str]:
        """Get all skills from enabled bundles."""
        skills = []
        for bundle in self._bundles.values():
            if bundle.enabled:
                skills.extend(bundle.skills)
        return list(set(skills))

    def list_bundles(self) -> list[dict]:
        """List all bundles."""
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
        """Delete a bundle."""
        if name in self._bundles:
            del self._bundles[name]
            self._save()
            return True
        return False
