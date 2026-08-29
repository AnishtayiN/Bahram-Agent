"""Skins and themes for Bahram Agent."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Theme:
    """A UI theme."""

    name: str
    description: str = ""
    colors: dict[str, str] = field(default_factory=dict)
    icons: dict[str, str] = field(default_factory=dict)


DEFAULT_THEMES = {
    "default": Theme(
        name="default",
        description="Default theme",
        colors={
            "primary": "#3B82F6",
            "secondary": "#10B981",
            "error": "#EF4444",
            "warning": "#F59E0B",
            "background": "#1F2937",
            "text": "#F9FAFB",
        },
    ),
    "dark": Theme(
        name="dark",
        description="Dark theme",
        colors={
            "primary": "#60A5FA",
            "secondary": "#34D399",
            "error": "#F87171",
            "warning": "#FBBF24",
            "background": "#111827",
            "text": "#F3F4F6",
        },
    ),
    "light": Theme(
        name="light",
        description="Light theme",
        colors={
            "primary": "#2563EB",
            "secondary": "#059669",
            "error": "#DC2626",
            "warning": "#D97706",
            "background": "#FFFFFF",
            "text": "#111827",
        },
    ),
    "solarized": Theme(
        name="solarized",
        description="Solarized theme",
        colors={
            "primary": "#268BD2",
            "secondary": "#2AA198",
            "error": "#DC322F",
            "warning": "#B58900",
            "background": "#002B36",
            "text": "#839496",
        },
    ),
    "monokai": Theme(
        name="monokai",
        description="Monokai theme",
        colors={
            "primary": "#A6E22E",
            "secondary": "#66D9EF",
            "error": "#F92672",
            "warning": "#FD971F",
            "background": "#272822",
            "text": "#F8F8F2",
        },
    ),
}


class ThemeManager:
    """Manage UI themes."""

    def __init__(self, themes_dir: str = "data/themes") -> None:
        self.themes_dir = Path(themes_dir)
        self.themes_dir.mkdir(parents=True, exist_ok=True)
        self._themes: dict[str, Theme] = DEFAULT_THEMES.copy()
        self._current: str = "default"
        self._load_custom_themes()

    def _load_custom_themes(self) -> None:
        """Load custom themes from disk."""
        for theme_file in self.themes_dir.glob("*.json"):
            try:
                with open(theme_file) as f:
                    data = json.load(f)
                theme = Theme(**data)
                self._themes[theme.name] = theme
            except Exception as e:
                logger.warning(f"Failed to load theme {theme_file}: {e}")

    def set_theme(self, name: str) -> bool:
        """Set the current theme."""
        if name in self._themes:
            self._current = name
            return True
        return False

    def get_theme(self) -> Theme:
        """Get the current theme."""
        return self._themes[self._current]

    def list_themes(self) -> list[dict]:
        """List all available themes."""
        return [
            {"name": t.name, "description": t.description}
            for t in self._themes.values()
        ]

    def create_theme(self, name: str, colors: dict, description: str = "") -> Theme:
        """Create a custom theme."""
        theme = Theme(name=name, description=description, colors=colors)
        self._themes[name] = theme

        # Save to disk
        theme_file = self.themes_dir / f"{name}.json"
        with open(theme_file, "w") as f:
            json.dump({
                "name": theme.name,
                "description": theme.description,
                "colors": theme.colors,
                "icons": theme.icons,
            }, f, indent=2)

        return theme

    def delete_theme(self, name: str) -> bool:
        """Delete a custom theme."""
        if name in DEFAULT_THEMES:
            return False  # Can't delete built-in themes
        if name in self._themes:
            del self._themes[name]
            theme_file = self.themes_dir / f"{name}.json"
            theme_file.unlink(missing_ok=True)
            return True
        return False
