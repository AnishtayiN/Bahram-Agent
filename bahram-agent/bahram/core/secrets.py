"""Secrets management for Bahram Agent."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class SecretEntry:
    """A secret entry."""

    name: str
    value: str
    description: str = ""
    category: str = "general"
    created_at: float = 0.0


class SecretsManager:
    """Manage secrets securely."""

    def __init__(self, data_dir: str = "data/secrets") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._secrets: dict[str, SecretEntry] = {}
        self._key = self._get_or_create_key()
        self._load()

    def _get_or_create_key(self) -> bytes:
        """Get or create encryption key."""
        key_file = self.data_dir / ".key"
        if key_file.exists():
            return base64.b64decode(key_file.read_text())
        else:
            key = os.urandom(32)
            key_file.write_text(base64.b64encode(key).decode())
            key_file.chmod(0o600)
            return key

    def _load(self) -> None:
        """Load secrets from disk."""
        secrets_file = self.data_dir / "secrets.enc"
        if secrets_file.exists():
            try:
                # Simple obfuscation (not real encryption)
                data = secrets_file.read_text()
                decoded = base64.b64decode(data)
                # XOR with key
                decrypted = bytes(b ^ self._key[i % len(self._key)] for i, b in enumerate(decoded))
                self._secrets = {
                    k: SecretEntry(**v)
                    for k, v in json.loads(decrypted).items()
                }
            except Exception as e:
                logger.warning(f"Failed to load secrets: {e}")

    def _save(self) -> None:
        """Save secrets to disk."""
        secrets_file = self.data_dir / "secrets.enc"
        data = json.dumps({
            k: {
                "name": s.name,
                "value": s.value,
                "description": s.description,
                "category": s.category,
                "created_at": s.created_at,
            }
            for k, s in self._secrets.items()
        })
        # XOR with key
        import time
        encrypted = bytes(b ^ self._key[i % len(self._key)] for i, b in enumerate(data.encode()))
        secrets_file.write_text(base64.b64encode(encrypted).decode())
        secrets_file.chmod(0o600)

    def set_secret(
        self,
        name: str,
        value: str,
        description: str = "",
        category: str = "general",
    ) -> None:
        """Set a secret."""
        import time
        self._secrets[name] = SecretEntry(
            name=name,
            value=value,
            description=description,
            category=category,
            created_at=time.time(),
        )
        self._save()

    def get_secret(self, name: str) -> Optional[str]:
        """Get a secret value."""
        entry = self._secrets.get(name)
        return entry.value if entry else None

    def get_secret_info(self, name: str) -> Optional[dict]:
        """Get secret info (without value)."""
        entry = self._secrets.get(name)
        if entry:
            return {
                "name": entry.name,
                "description": entry.description,
                "category": entry.category,
                "created_at": entry.created_at,
            }
        return None

    def delete_secret(self, name: str) -> bool:
        """Delete a secret."""
        if name in self._secrets:
            del self._secrets[name]
            self._save()
            return True
        return False

    def list_secrets(self, category: str = None) -> list[dict]:
        """List secrets (without values)."""
        secrets = list(self._secrets.values())
        if category:
            secrets = [s for s in secrets if s.category == category]
        return [
            {
                "name": s.name,
                "description": s.description,
                "category": s.category,
            }
            for s in secrets
        ]

    def import_from_env(self, prefix: str = "") -> int:
        """Import secrets from environment variables."""
        count = 0
        for key, value in os.environ.items():
            if prefix and not key.startswith(prefix):
                continue
            if key.startswith(("SECRET", "TOKEN", "KEY", "PASSWORD", "API_")):
                self.set_secret(key, value, description="Imported from environment")
                count += 1
        return count
