"""Personality and SOUL.md system for Bahram Agent."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Built-in personalities
PERSONALITIES = {
    "default": {
        "name": "Bahram",
        "description": "A helpful and capable AI assistant",
        "system_prompt": "You are Bahram, an advanced AI agent. You are helpful, capable, and strive to complete tasks thoroughly.",
    },
    "pirate": {
        "name": "Bahram the Pirate",
        "description": "A pirate-themed assistant",
        "system_prompt": "You are Bahram, a pirate AI! Arr! You speak like a pirate and love adventure. You're still helpful but with a pirate twist.",
    },
    "scholar": {
        "name": "Bahram the Scholar",
        "description": "A scholarly, academic assistant",
        "system_prompt": "You are Bahram, a scholarly AI. You provide detailed, well-researched answers with citations. You value accuracy and intellectual rigor.",
    },
    "coder": {
        "name": "Bahram the Coder",
        "description": "A coding-focused assistant",
        "system_prompt": "You are Bahram, an expert programmer. You write clean, efficient code and follow best practices. You explain technical concepts clearly.",
    },
    "creative": {
        "name": "Bahram the Creative",
        "description": "A creative and artistic assistant",
        "system_prompt": "You are Bahram, a creative AI. You think outside the box, use vivid language, and bring imagination to every task.",
    },
}


class PersonalityManager:
    """Manage agent personality and SOUL.md."""

    def __init__(self, project_dir: str = ".") -> None:
        self.project_dir = Path(project_dir)
        self._current_personality: str = "default"
        self._soul_content: Optional[str] = None
        self._custom_system_prompt: Optional[str] = None

    def set_personality(self, name: str) -> bool:
        """Set the current personality."""
        if name in PERSONALITIES:
            self._current_personality = name
            self._custom_system_prompt = None  # Clear custom prompt
            logger.info(f"Set personality: {name}")
            return True
        return False

    def set_custom_prompt(self, prompt: str) -> None:
        """Set a custom system prompt."""
        self._custom_system_prompt = prompt
        self._current_personality = "custom"

    def get_system_prompt_addition(self) -> str:
        """Get the system prompt addition for the current personality."""
        # Custom prompt takes priority
        if self._custom_system_prompt:
            return f"\n\n{self._custom_system_prompt}"

        # Check for SOUL.md
        soul = self._load_soul_md()
        if soul:
            return f"\n\n{self._load_personality_prompt()}\n\n{self._load_soul_md()}"

        # Use built-in personality
        return f"\n\n{self._load_personality_prompt()}"

    def _load_personality_prompt(self) -> str:
        """Get the prompt for current personality."""
        if self._current_personality == "custom":
            return self._custom_system_prompt or ""

        personality = PERSONALITIES.get(self._current_personality, PERSONALITIES["default"])
        return f"## Personality: {personality['name']}\n\n{personality['system_prompt']}"

    def _load_soul_md(self) -> Optional[str]:
        """Load SOUL.md from project."""
        soul_path = self.project_dir / "SOUL.md"
        if soul_path.exists():
            try:
                return soul_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to read SOUL.md: {e}")
        return None

    def list_personalities(self) -> list[dict]:
        """List available personalities."""
        return [
            {"name": name, "description": p["description"]}
            for name, p in PERSONALITIES.items()
        ]

    def get_current(self) -> str:
        """Get current personality name."""
        return self._current_personality

    def clear_cache(self) -> None:
        """Clear cached SOUL.md content."""
        self._soul_content = None
