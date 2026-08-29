"""DM pairing authorization for Bahram Agent."""

from __future__ import annotations

import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PairingRequest:
    """A pending pairing request."""

    platform: str
    user_id: str
    code: str
    created_at: float = field(default_factory=time.time)
    attempts: int = 0


class PairingManager:
    """Manage DM pairing authorization."""

    CODE_LENGTH = 8
    CODE_TTL = 3600  # 1 hour
    MAX_ATTEMPTS = 5
    LOCKOUT_DURATION = 3600  # 1 hour
    RATE_LIMIT = 600  # 10 minutes

    def __init__(self, data_dir: str = "data/pairing") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._pending: dict[str, PairingRequest] = {}
        self._approved: dict[str, set[str]] = {}
        self._rate_limits: dict[str, float] = {}
        self._lockouts: dict[str, float] = {}
        self._load_data()

    def _load_data(self) -> None:
        """Load pairing data."""
        pending_file = self.data_dir / "pending.json"
        if pending_file.exists():
            try:
                with open(pending_file) as f:
                    data = json.load(f)
                for item in data:
                    pr = PairingRequest(**item)
                    key = f"{pr.platform}:{pr.user_id}"
                    self._pending[key] = pr
            except Exception as e:
                logger.warning(f"Failed to load pending: {e}")

        approved_file = self.data_dir / "approved.json"
        if approved_file.exists():
            try:
                with open(approved_file) as f:
                    data = json.load(f)
                for platform, users in data.items():
                    self._approved[platform] = set(users)
            except Exception as e:
                logger.warning(f"Failed to load approved: {e}")

    def _save_data(self) -> None:
        """Save pairing data."""
        # Save pending
        pending_file = self.data_dir / "pending.json"
        data = [
            {
                "platform": pr.platform,
                "user_id": pr.user_id,
                "code": pr.code,
                "created_at": pr.created_at,
                "attempts": pr.attempts,
            }
            for pr in self._pending.values()
        ]
        with open(pending_file, "w") as f:
            json.dump(data, f, indent=2)

        # Save approved
        approved_file = self.data_dir / "approved.json"
        data = {platform: list(users) for platform, users in self._approved.items()}
        with open(approved_file, "w") as f:
            json.dump(data, f, indent=2)

    def request_pairing(self, platform: str, user_id: str) -> Optional[str]:
        """Request a pairing code."""
        key = f"{platform}:{user_id}"

        # Check rate limit
        if key in self._rate_limits:
            if time.time() - self._rate_limits[key] < self.RATE_LIMIT:
                return None

        # Check lockout
        if key in self._lockouts:
            if time.time() - self._lockouts[key] < self.LOCKOUT_DURATION:
                return None
            del self._lockouts[key]

        # Generate code
        code = secrets.token_urlsafe(self.CODE_LENGTH)[:self.CODE_LENGTH].upper()
        self._pending[key] = PairingRequest(
            platform=platform,
            user_id=user_id,
            code=code,
        )
        self._rate_limits[key] = time.time()
        self._save_data()
        return code

    def approve_pairing(self, platform: str, code: str) -> bool:
        """Approve a pairing code."""
        for key, pr in self._pending.items():
            if pr.platform == platform and pr.code == code:
                # Check expiry
                if time.time() - pr.created_at > self.CODE_TTL:
                    del self._pending[key]
                    self._save_data()
                    return False

                # Approve
                if platform not in self._approved:
                    self._approved[platform] = set()
                self._approved[platform].add(pr.user_id)
                del self._pending[key]
                self._save_data()
                return True
        return False

    def is_approved(self, platform: str, user_id: str) -> bool:
        """Check if a user is approved."""
        return user_id in self._approved.get(platform, set())

    def revoke_access(self, platform: str, user_id: str) -> bool:
        """Revoke a user's access."""
        if platform in self._approved:
            self._approved[platform].discard(user_id)
            self._save_data()
            return True
        return False

    def list_pending(self) -> list[dict]:
        """List pending pairing requests."""
        return [
            {"platform": pr.platform, "user_id": pr.user_id, "code": pr.code}
            for pr in self._pending.values()
        ]

    def list_approved(self) -> dict[str, list[str]]:
        """List approved users."""
        return {p: list(u) for p, u in self._approved.items()}
