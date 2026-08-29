"""Secrets management for Bahram Agent."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SecretsManager:
    """Manage secrets and environment variables."""

    def __init__(self, env_dir: str = "data/secrets") -> None:
        self.env_dir = Path(env_dir)
        self.env_dir.mkdir(parents=True, exist_ok=True)
        self._secrets: dict[str, str] = {}
        self._load_secrets()

    def _load_secrets(self) -> None:
        """Load secrets from .env file."""
        env_file = self.env_dir / ".env"
        if env_file.exists():
            try:
                with open(env_file) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            self._secrets[key.strip()] = value.strip()
            except Exception as e:
                logger.warning(f"Failed to load secrets: {e}")

    def _save_secrets(self) -> None:
        """Save secrets to .env file."""
        env_file = self.env_dir / ".env"
        with open(env_file, "w") as f:
            for key, value in self._secrets.items():
                f.write(f"{key}={value}\n")
        # Restrict permissions
        try:
            os.chmod(env_file, 0o600)
        except Exception:
            pass

    def get(self, key: str, default: str = "") -> str:
        """Get a secret value."""
        # Check env first
        env_value = os.environ.get(key)
        if env_value:
            return env_value
        return self._secrets.get(key, default)

    def set(self, key: str, value: str) -> None:
        """Set a secret value."""
        self._secrets[key] = value
        self._save_secrets()

    def delete(self, key: str) -> bool:
        """Delete a secret."""
        if key in self._secrets:
            del self._secrets[key]
            self._save_secrets()
            return True
        return False

    def list_keys(self) -> list[str]:
        """List all secret keys."""
        return list(self._secrets.keys())

    def get_redacted(self) -> dict[str, str]:
        """Get secrets with values redacted."""
        return {k: "***" for k in self._secrets}

    def get_provider_key(self, provider: str) -> str:
        """Get API key for a provider."""
        key_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "groq": "GROQ_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "google": "GOOGLE_API_KEY",
            "huggingface": "HF_API_KEY",
            "nous": "NOUS_API_KEY",
            "nvidia": "NVIDIA_API_KEY",
            "xiaomi": "XIAOMI_API_KEY",
            "minimax": "MINIMAX_API_KEY",
            "kimi": "KIMI_API_KEY",
            "zhipu": "ZHIPU_API_KEY",
            "telegram": "TELEGRAM_BOT_TOKEN",
            "discord": "DISCORD_BOT_TOKEN",
            "slack": "SLACK_BOT_TOKEN",
        }
        env_key = key_map.get(provider.lower(), f"{provider.upper()}_API_KEY")
        return self.get(env_key)
