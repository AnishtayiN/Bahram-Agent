"""
Themes.

Public objects: ``Theme``, ``ThemeManager``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Theme:
    """
    Theme.

    Attributes:
        name (str): name of the object.
        display_name (str): display name string.
        description (str): human readable description.
        colors (dict[str, str]): mapping of colors.
        emoji (dict[str, str]): mapping of emoji.
        is_default (bool): when ``True``, enable is default.
    """

    name: str
    display_name: str
    description: str = ""
    colors: dict[str, str] = field(default_factory=dict)
    emoji: dict[str, str] = field(default_factory=dict)
    is_default: bool = False


DEFAULT_THEME = Theme(
    name="default",
    display_name="Bahram Default",
    description="Default Bahram theme",
    colors={
        "primary": "#FF6B35",
        "secondary": "#4ECDC4",
        "background": "#1A1A2E",
        "text": "#FFFFFF",
        "error": "#FF6B6B",
        "success": "#4ECDC4",
        "warning": "#FFD93D",
    },
    emoji={
        "thinking": "🤔",
        "working": "⚙️",
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "info": "ℹ️",
    },
    is_default=True,
)

DARK_THEME = Theme(
    name="dark",
    display_name="Midnight",
    description="Dark theme for night owls",
    colors={
        "primary": "#BB86FC",
        "secondary": "#03DAC6",
        "background": "#121212",
        "text": "#FFFFFF",
        "error": "#CF6679",
        "success": "#03DAC6",
        "warning": "#FFD93D",
    },
)

LIGHT_THEME = Theme(
    name="light",
    display_name="Sunlight",
    description="Light theme",
    colors={
        "primary": "#6200EE",
        "secondary": "#03DAC6",
        "background": "#FFFFFF",
        "text": "#000000",
        "error": "#B00020",
        "success": "#03DAC6",
        "warning": "#F57C00",
    },
)

PERSIAN_THEME = Theme(
    name="persian",
    display_name="Persian Night",
    description="Inspired by Persian architecture",
    colors={
        "primary": "#C41E3A",
        "secondary": "#FFD700",
        "background": "#1A1A2E",
        "text": "#FFFFFF",
        "error": "#FF4444",
        "success": "#4ECDC4",
        "warning": "#FFD700",
    },
    emoji={
        "thinking": "🌙",
        "working": "⭐",
        "success": "✨",
        "error": "💫",
        "warning": "🌟",
        "info": "🪐",
    },
)


class ThemeManager:
    """
    Theme manager.
    """

    def __init__(self, config_dir: str = "config") -> None:
        """
        Initialise a ThemeManager instance.

        Args:
            config_dir (str): config dir string. Defaults to ``'config'``.
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self._themes: dict[str, Theme] = {
            DEFAULT_THEME.name: DEFAULT_THEME,
            DARK_THEME.name: DARK_THEME,
            LIGHT_THEME.name: LIGHT_THEME,
            PERSIAN_THEME.name: PERSIAN_THEME,
        }
        self._current_theme: str = DEFAULT_THEME.name
        self._load()

    def _load(self) -> None:
        theme_file = self.config_dir / "theme.json"
        if theme_file.exists():
            try:
                with open(theme_file) as f:
                    data = json.load(f)
                self._current_theme = data.get("current_theme", "default")
            except Exception as e:
                logger.warning(f"Failed to load theme config: {e}")

    def _save(self) -> None:
        theme_file = self.config_dir / "theme.json"
        with open(theme_file, "w") as f:
            json.dump({"current_theme": self._current_theme}, f, indent=2)

    def get_theme(self, name: str = None) -> Theme:
        """
        Return the theme.

        Args:
            name (str): name of the object. Defaults to ``None``.

        Returns:
            Theme: the resulting Theme.
        """
        return self._themes.get(name or self._current_theme, DEFAULT_THEME)

    def set_theme(self, name: str) -> bool:
        """
        Set the theme.

        Args:
            name (str): name of the object.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        if name in self._themes:
            self._current_theme = name
            self._save()
            return True
        return False

    def list_themes(self) -> list[dict]:
        """
        List themes.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        return [
            {
                "name": t.name,
                "display_name": t.display_name,
                "description": t.description,
                "is_default": t.is_default,
                "is_current": t.name == self._current_theme,
            }
            for t in self._themes.values()
        ]

    def add_theme(self, theme: Theme) -> None:
        """
        Add theme.

        Args:
            theme (Theme): theme.
        """
        self._themes[theme.name] = theme

    def get_color(self, key: str) -> str:
        """
        Return the color.

        Args:
            key (str): key string.

        Returns:
            str: the rendered string.
        """
        theme = self.get_theme()
        return theme.colors.get(key, "#000000")

    def get_emoji(self, key: str) -> str:
        """
        Return the emoji.

        Args:
            key (str): key string.

        Returns:
            str: the rendered string.
        """
        theme = self.get_theme()
        return theme.emoji.get(key, "")
