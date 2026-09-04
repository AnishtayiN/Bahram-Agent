from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AgentProfile:
    name: str
    display_name: str
    description: str = ""
    system_prompt: str = ""
    personality: str = ""
    model: str = ""
    provider: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    is_default: bool = False
    metadata: dict = field(default_factory=dict)


class ProfileManager:
    def __init__(self, data_dir: str = "data/profiles") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: dict[str, AgentProfile] = {}
        self._current_profile: str = "default"
        self._load()

    def _load(self) -> None:
        profiles_file = self.data_dir / "profiles.json"
        if profiles_file.exists():
            try:
                with open(profiles_file) as f:
                    data = json.load(f)
                for profile_data in data:
                    profile = AgentProfile(**profile_data)
                    self._profiles[profile.name] = profile
            except Exception as e:
                logger.warning(f"Failed to load profiles: {e}")

    def _save(self) -> None:
        profiles_file = self.data_dir / "profiles.json"
        data = [
            {
                "name": p.name,
                "display_name": p.display_name,
                "description": p.description,
                "system_prompt": p.system_prompt,
                "personality": p.personality,
                "model": p.model,
                "provider": p.provider,
                "temperature": p.temperature,
                "max_tokens": p.max_tokens,
                "is_default": p.is_default,
                "metadata": p.metadata,
            }
            for p in self._profiles.values()
        ]
        with open(profiles_file, "w") as f:
            json.dump(data, f, indent=2)

    def create_profile(
        self,
        name: str,
        display_name: str,
        description: str = "",
        system_prompt: str = "",
        personality: str = "",
        model: str = "",
        provider: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AgentProfile:
        profile = AgentProfile(
            name=name,
            display_name=display_name,
            description=description,
            system_prompt=system_prompt,
            personality=personality,
            model=model,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self._profiles[name] = profile
        self._save()
        return profile

    def get_profile(self, name: str) -> AgentProfile | None:
        return self._profiles.get(name)

    def set_current(self, name: str) -> bool:
        if name in self._profiles:
            self._current_profile = name
            return True
        return False

    def get_current(self) -> AgentProfile:
        return self._profiles.get(self._current_profile, self._profiles.get("default"))

    def list_profiles(self) -> list[dict]:
        return [
            {
                "name": p.name,
                "display_name": p.display_name,
                "description": p.description,
                "is_default": p.is_default,
                "is_current": p.name == self._current_profile,
            }
            for p in self._profiles.values()
        ]

    def delete_profile(self, name: str) -> bool:
        if name in self._profiles and name != "default":
            del self._profiles[name]
            if self._current_profile == name:
                self._current_profile = "default"
            self._save()
            return True
        return False

    def update_profile(self, name: str, **kwargs) -> bool:
        profile = self._profiles.get(name)
        if profile:
            for key, value in kwargs.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
            self._save()
            return True
        return False
