"""Skill bundles for Bahram Agent."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SkillBundle:
    """A skill bundle grouping multiple skills."""

    name: str
    description: str = ""
    skills: list[str] = field(default_factory=list)
    instruction: str = ""


class BundleManager:
    """Manage skill bundles."""

    def __init__(self, bundles_dir: str = "data/skill-bundles") -> None:
        self.bundles_dir = Path(bundles_dir)
        self.bundles_dir.mkdir(parents=True, exist_ok=True)
        self._bundles: dict[str, SkillBundle] = {}
        self._load_bundles()

    def _load_bundles(self) -> None:
        """Load bundles from disk."""
        import json
        for bundle_file in self.bundles_dir.glob("*.json"):
            try:
                with open(bundle_file) as f:
                    data = json.load(f)
                bundle = SkillBundle(**data)
                self._bundles[bundle.name] = bundle
            except Exception as e:
                logger.warning(f"Failed to load bundle {bundle_file}: {e}")

    def create_bundle(
        self,
        name: str,
        skills: list[str],
        description: str = "",
        instruction: str = "",
    ) -> SkillBundle:
        """Create a new bundle."""
        import json
        bundle = SkillBundle(
            name=name,
            description=description,
            skills=skills,
            instruction=instruction,
        )
        self._bundles[name] = bundle

        # Save to disk
        bundle_file = self.bundles_dir / f"{name}.json"
        with open(bundle_file, "w") as f:
            json.dump({
                "name": bundle.name,
                "description": bundle.description,
                "skills": bundle.skills,
                "instruction": bundle.instruction,
            }, f, indent=2)

        return bundle

    def delete_bundle(self, name: str) -> bool:
        """Delete a bundle."""
        if name in self._bundles:
            del self._bundles[name]
            bundle_file = self.bundles_dir / f"{name}.json"
            bundle_file.unlink(missing_ok=True)
            return True
        return False

    def get_bundle(self, name: str) -> Optional[SkillBundle]:
        """Get a bundle by name."""
        return self._bundles.get(name)

    def list_bundles(self) -> list[SkillBundle]:
        """List all bundles."""
        return list(self._bundles.values())

    def render_list(self) -> str:
        """Render bundles as markdown."""
        bundles = self.list_bundles()
        if not bundles:
            return "No bundles configured."

        parts = []
        for b in bundles:
            skills_str = ", ".join(b.skills)
            parts.append(f"**{b.name}**: {b.description}\n  Skills: {skills_str}")

        return "\n".join(parts)
