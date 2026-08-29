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
    ""

    name: str
    value: str
    description: str = ""
    category: str = "general"
    created_at: float = 0.0

class SecretsManager:
    ""

    def __init__(self, data_dir: str = "data/secrets") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._secrets: dict[str, SecretEntry] = {}
        self._key = self._get_or_create_key()
        self._load()

    def _get_or_create_key(self) -> bytes:
        ""
        key_file = self.data_dir / ".key"
        if key_file.exists():
            return base64.b64decode(key_file.read_text())
        else:
            key = os.urandom(32)
            key_file.write_text(base64.b64encode(key).decode())
            key_file.chmod(0o600)
            return key

    def _load(self) -> None:
        ""
        secrets_file = self.data_dir / "secrets.enc"
        if secrets_file.exists():
            try:

                data = secrets_file.read_text()
                decoded = base64.b64decode(data)

                decrypted = bytes(b ^ self._key[i % len(self._key)] for i, b in enumerate(decoded))
                self._secrets = {
                    k: SecretEntry(**v)
                    for k, v in json.loads(decrypted).items()
                }
            except Exception as e:
                logger.warning(f"Failed to load secrets: {e}")

    def _save(self) -> None:
        ""
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
        ""
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
        ""
        entry = self._secrets.get(name)
        return entry.value if entry else None

    def get_secret_info(self, name: str) -> Optional[dict]:
        ""
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
        ""
        if name in self._secrets:
            del self._secrets[name]
            self._save()
            return True
        return False

    def list_secrets(self, category: str = None) -> list[dict]:
        ""
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
        ""
        count = 0
        for key, value in os.environ.items():
            if prefix and not key.startswith(prefix):
                continue
            if key.startswith(("SECRET", "TOKEN", "KEY", "PASSWORD", "API_")):
                self.set_secret(key, value, description="Imported from environment")
                count += 1
        return count
