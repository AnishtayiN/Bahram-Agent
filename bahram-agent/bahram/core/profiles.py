"""
Profiles.

Public objects: ``AgentProfile``, ``ProfileManager``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class AgentProfile:
    """
    Agent profile.

    Attributes:
        name (str): name of the object.
        display_name (str): display name string.
        description (str): human readable description.
        system_prompt (str): system prompt string.
        personality (str): personality string.
        model (str): model identifier in ``provider/model`` form.
        provider (str): provider string.
        temperature (float): numeric value for temperature.
        max_tokens (int): numeric value for max tokens.
        is_default (bool): when ``True``, enable is default.
        metadata (dict): mapping of metadata.
    """

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
    """
    Profile manager.
    """

    def __init__(self, data_dir: str = "data/profiles") -> None:
        """
        Initialise a ProfileManager instance.

        Args:
            data_dir (str): directory that holds the on-disk state. Defaults to ``'data/profiles'``.
        """
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
        """
        Create profile.

        Args:
            name (str): name of the object.
            display_name (str): display name string.
            description (str): human readable description. Defaults to ``''``.
            system_prompt (str): system prompt string. Defaults to ``''``.
            personality (str): personality string. Defaults to ``''``.
            model (str): model identifier in ``provider/model`` form. Defaults to ``''``.
            provider (str): provider string. Defaults to ``''``.
            temperature (float): numeric value for temperature. Defaults to ``0.7``.
            max_tokens (int): numeric value for max tokens. Defaults to ``4096``.

        Returns:
            AgentProfile: the resulting AgentProfile.
        """
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
        """
        Return the profile.

        Args:
            name (str): name of the object.

        Returns:
            AgentProfile | None: the resulting object, or ``None`` when it is not available.
        """
        return self._profiles.get(name)

    def set_current(self, name: str) -> bool:
        """
        Set the current.

        Args:
            name (str): name of the object.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        if name in self._profiles:
            self._current_profile = name
            return True
        return False

    def get_current(self) -> AgentProfile:
        """
        Return the current.

        Returns:
            AgentProfile: the resulting AgentProfile.
        """
        return self._profiles.get(self._current_profile, self._profiles.get("default"))

    def list_profiles(self) -> list[dict]:
        """
        List profiles.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
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
        """
        Delete profile.

        Args:
            name (str): name of the object.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        if name in self._profiles and name != "default":
            del self._profiles[name]
            if self._current_profile == name:
                self._current_profile = "default"
            self._save()
            return True
        return False

    def update_profile(self, name: str, **kwargs) -> bool:
        """
        Update profile.

        Args:
            name (str): name of the object.
            **kwargs: keyword arguments forwarded to the implementation.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        profile = self._profiles.get(name)
        if profile:
            for key, value in kwargs.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)
            self._save()
            return True
        return False
