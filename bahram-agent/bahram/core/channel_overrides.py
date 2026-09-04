"""
Channel overrides.

Public objects: ``ChannelOverride``, ``ChannelOverrideManager``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ChannelOverride:
    """
    Channel override.

    Attributes:
        channel_id (str): channel id string.
        model (str): model identifier in ``provider/model`` form.
        provider (str): provider string.
        system_prompt (str): system prompt string.
        personality (str): personality string.
    """

    channel_id: str
    model: str = ""
    provider: str = ""
    system_prompt: str = ""
    personality: str = ""


class ChannelOverrideManager:
    """
    Channel override manager.
    """

    def __init__(self, config_dir: str = "data/gateway") -> None:
        """
        Initialise a ChannelOverrideManager instance.

        Args:
            config_dir (str): config dir string. Defaults to ``'data/gateway'``.
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._overrides: dict[str, dict[str, ChannelOverride]] = {}
        self._load_overrides()

    def _load_overrides(self) -> None:
        overrides_file = self.config_dir / "channel_overrides.json"
        if overrides_file.exists():
            try:
                with open(overrides_file) as f:
                    data = json.load(f)
                for platform, channels in data.items():
                    self._overrides[platform] = {}
                    for channel_id, override_data in channels.items():
                        self._overrides[platform][channel_id] = ChannelOverride(**override_data)
            except Exception as e:
                logger.warning(f"Failed to load overrides: {e}")

    def _save_overrides(self) -> None:
        overrides_file = self.config_dir / "channel_overrides.json"
        data = {}
        for platform, channels in self._overrides.items():
            data[platform] = {}
            for channel_id, override in channels.items():
                data[platform][channel_id] = {
                    "channel_id": override.channel_id,
                    "model": override.model,
                    "provider": override.provider,
                    "system_prompt": override.system_prompt,
                    "personality": override.personality,
                }
        with open(overrides_file, "w") as f:
            json.dump(data, f, indent=2)

    def set_override(
        self,
        platform: str,
        channel_id: str,
        model: str = "",
        provider: str = "",
        system_prompt: str = "",
        personality: str = "",
    ) -> ChannelOverride:
        """
        Set the override.

        Args:
            platform (str): platform string.
            channel_id (str): channel id string.
            model (str): model identifier in ``provider/model`` form. Defaults to ``''``.
            provider (str): provider string. Defaults to ``''``.
            system_prompt (str): system prompt string. Defaults to ``''``.
            personality (str): personality string. Defaults to ``''``.

        Returns:
            ChannelOverride: the resulting ChannelOverride.
        """
        if platform not in self._overrides:
            self._overrides[platform] = {}

        override = ChannelOverride(
            channel_id=channel_id,
            model=model,
            provider=provider,
            system_prompt=system_prompt,
            personality=personality,
        )
        self._overrides[platform][channel_id] = override
        self._save_overrides()
        return override

    def get_override(self, platform: str, channel_id: str) -> ChannelOverride | None:
        """
        Return the override.

        Args:
            platform (str): platform string.
            channel_id (str): channel id string.

        Returns:
            ChannelOverride | None: the resulting object, or ``None`` when it is not available.
        """
        return self._overrides.get(platform, {}).get(channel_id)

    def remove_override(self, platform: str, channel_id: str) -> bool:
        """
        Remove override.

        Args:
            platform (str): platform string.
            channel_id (str): channel id string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        if platform in self._overrides and channel_id in self._overrides[platform]:
            del self._overrides[platform][channel_id]
            self._save_overrides()
            return True
        return False

    def list_overrides(self, platform: str = None) -> list[dict]:
        """
        List overrides.

        Args:
            platform (str): platform string. Defaults to ``None``.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        results = []
        platforms = [platform] if platform else self._overrides.keys()
        for p in platforms:
            for channel_id, override in self._overrides.get(p, {}).items():
                results.append(
                    {
                        "platform": p,
                        "channel_id": channel_id,
                        "model": override.model,
                        "system_prompt": override.system_prompt[:50]
                        if override.system_prompt
                        else "",
                    }
                )
        return results
