from __future__ import annotations

import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class PairingRequest:

    code: str
    platform: str
    user_id: str
    timestamp: float
    expires_at: float
    used: bool = False

class DMPairingManager:

    def __init__(self, data_dir: str = "data/security") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._requests: list[PairingRequest] = []
        self._paired_users: dict[str, dict] = {}
        self._code_length = 8
        self._expiry_seconds = 300
        self._load()

    def _load(self) -> None:
        pairing_file = self.data_dir / "dm_pairing.json"
        if pairing_file.exists():
            try:
                with open(pairing_file) as f:
                    data = json.load(f)
                self._paired_users = data.get("paired_users", {})
            except Exception as e:
                logger.warning(f"Failed to load pairing data: {e}")

    def _save(self) -> None:
        pairing_file = self.data_dir / "dm_pairing.json"
        data = {"paired_users": self._paired_users}
        with open(pairing_file, "w") as f:
            json.dump(data, f, indent=2)

    def generate_code(self, platform: str, user_id: str) -> str:
        code = secrets.token_urlsafe(self._code_length)[: self._code_length]
        request = PairingRequest(
            code=code,
            platform=platform,
            user_id=user_id,
            timestamp=time.time(),
            expires_at=time.time() + self._expiry_seconds,
        )
        self._requests.append(request)
        return code

    def verify_code(self, code: str) -> Optional[dict]:
        for request in self._requests:
            if (
                request.code == code
                and not request.used
                and time.time() < request.expires_at
            ):
                request.used = True

                user_key = f"{request.platform}:{request.user_id}"
                self._paired_users[user_key] = {
                    "platform": request.platform,
                    "user_id": request.user_id,
                    "paired_at": time.time(),
                }
                self._save()
                return self._paired_users[user_key]

        return None

    def is_paired(self, platform: str, user_id: str) -> bool:
        user_key = f"{platform}:{user_id}"
        return user_key in self._paired_users

    def unpair(self, platform: str, user_id: str) -> bool:
        user_key = f"{platform}:{user_id}"
        if user_key in self._paired_users:
            del self._paired_users[user_key]
            self._save()
            return True
        return False

    def list_paired(self) -> list[dict]:
        return [
            {
                "platform": v["platform"],
                "user_id": v["user_id"],
                "paired_at": v["paired_at"],
            }
            for v in self._paired_users.values()
        ]

    def cleanup_expired(self) -> int:
        now = time.time()
        expired = [r for r in self._requests if r.expires_at < now or r.used]
        for r in expired:
            self._requests.remove(r)
        return len(expired)
