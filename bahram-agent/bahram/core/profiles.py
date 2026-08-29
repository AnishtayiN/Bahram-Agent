"""Profile management for Bahram Agent."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Profile:
    """An agent profile."""

    name: str
    description: str = ""
    model: str = ""
    provider: str = ""
    personality: str = "default"
    config: dict = field(default_factory=dict)
    skills: list[str] = field(default_factory=list)
    mcp_servers: dict = field(default_factory=dict)


class ProfileManager:
    """Manage multiple agent profiles."""

    def __init__(self, data_dir: str = "data/profiles") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: dict[str, Profile] = {}
        self._active: str = "default"
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load profiles from disk."""
        for profile_file in self.data_dir.glob("*.json"):
            try:
                with open(profile_file) as f:
                    data = json.load(f)
                profile = Profile(**data)
                self._profiles[profile.name] = profile
            except Exception as e:
                logger.warning(f"Failed to load profile {profile_file}: {e}")

    def _save_profile(self, profile: Profile) -> None:
        """Save a profile."""
        profile_file = self.data_dir / f"{profile.name}.json"
        with open(profile_file, "w") as f:
            json.dump({
                "name": profile.name,
                "description": profile.description,
                "model": profile.model,
                "provider": profile.provider,
                "personality": profile.personality,
                "config": profile.config,
                "skills": profile.skills,
                "mcp_servers": profile.mcp_servers,
            }, f, indent=2)

    def create_profile(self, name: str, **kwargs) -> Profile:
        """Create a new profile."""
        profile = Profile(name=name, **kwargs)
        self._profiles[name] = profile
        self._save_profile(profile)
        return profile

    def get_profile(self, name: str) -> Optional[Profile]:
        """Get a profile by name."""
        return self._profiles.get(name)

    def set_active(self, name: str) -> bool:
        """Set the active profile."""
        if name in self._profiles:
            self._active = name
            return True
        return False

    def get_active(self) -> Profile:
        """Get the active profile."""
        return self._profiles.get(self._active, Profile(name="default"))

    def list_profiles(self) -> list[dict]:
        """List all profiles."""
        return [
            {"name": p.name, "description": p.description, "active": p.name == self._active}
            for p in self._profiles.values()
        ]

    def delete_profile(self, name: str) -> bool:
        """Delete a profile."""
        if name in self._profiles and name != "default":
            del self._profiles[name]
            profile_file = self.data_dir / f"{name}.json"
            profile_file.unlink(missing_ok=True)
            return True
        return False

    def export_profile(self, name: str) -> Optional[str]:
        """Export profile as JSON."""
        profile = self._profiles.get(name)
        if profile:
            return json.dumps({
                "name": profile.name,
                "description": profile.description,
                "model": profile.model,
                "provider": profile.provider,
                "personality": profile.personality,
                "config": profile.config,
                "skills": profile.skills,
            }, indent=2)
        return None

    def import_profile(self, data: str) -> Optional[Profile]:
        """Import profile from JSON."""
        try:
            profile_data = json.loads(data)
            profile = Profile(**profile_data)
            self._profiles[profile.name] = profile
            self._save_profile(profile)
            return profile
        except Exception as e:
            logger.error(f"Failed to import profile: {e}")
            return None
