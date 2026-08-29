"""Delivery ledger for crash recovery in Bahram Agent."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DeliveryEntry:
    """A delivery ledger entry."""

    id: str
    platform: str
    chat_id: str
    response: str
    status: str = "pending"  # pending, sent, failed, recovered
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    sent_at: Optional[str] = None
    attempts: int = 0


class DeliveryLedger:
    """Track message delivery for crash recovery."""

    MAX_ATTEMPTS = 3
    MAX_AGE_HOURS = 24
    RETENTION_DAYS = 7

    def __init__(self, data_dir: str = "data/delivery") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, DeliveryEntry] = {}
        self._load_entries()

    def _load_entries(self) -> None:
        """Load entries from disk."""
        ledger_file = self.data_dir / "ledger.json"
        if ledger_file.exists():
            try:
                with open(ledger_file) as f:
                    data = json.load(f)
                for item in data:
                    entry = DeliveryEntry(**item)
                    self._entries[entry.id] = entry
            except Exception as e:
                logger.warning(f"Failed to load ledger: {e}")

    def _save_entries(self) -> None:
        """Save entries to disk."""
        ledger_file = self.data_dir / "ledger.json"
        data = [
            {
                "id": e.id,
                "platform": e.platform,
                "chat_id": e.chat_id,
                "response": e.response,
                "status": e.status,
                "created_at": e.created_at,
                "sent_at": e.sent_at,
                "attempts": e.attempts,
            }
            for e in self._entries.values()
        ]
        with open(ledger_file, "w") as f:
            json.dump(data, f, indent=2)

    def record_delivery(
        self,
        entry_id: str,
        platform: str,
        chat_id: str,
        response: str,
    ) -> DeliveryEntry:
        """Record a delivery attempt."""
        entry = DeliveryEntry(
            id=entry_id,
            platform=platform,
            chat_id=chat_id,
            response=response,
        )
        self._entries[entry_id] = entry
        self._save_entries()
        return entry

    def mark_sent(self, entry_id: str) -> None:
        """Mark delivery as successful."""
        entry = self._entries.get(entry_id)
        if entry:
            entry.status = "sent"
            entry.sent_at = datetime.now().isoformat()
            self._save_entries()

    def mark_failed(self, entry_id: str) -> None:
        """Mark delivery as failed."""
        entry = self._entries.get(entry_id)
        if entry:
            entry.attempts += 1
            if entry.attempts >= self.MAX_ATTEMPTS:
                entry.status = "failed"
            self._save_entries()

    def get_recoverable(self) -> list[DeliveryEntry]:
        """Get entries that need recovery."""
        now = datetime.now()
        recoverable = []

        for entry in self._entries.values():
            if entry.status == "sent":
                continue

            created = datetime.fromisoformat(entry.created_at)
            age = now - created

            if age > timedelta(hours=self.MAX_AGE_HOURS):
                continue

            if entry.attempts < self.MAX_ATTEMPTS:
                recoverable.append(entry)

        return recoverable

    def cleanup_old(self) -> int:
        """Clean up old entries."""
        cutoff = datetime.now() - timedelta(days=self.RETENTION_DAYS)
        to_delete = []

        for entry_id, entry in self._entries.items():
            created = datetime.fromisoformat(entry.created_at)
            if created < cutoff:
                to_delete.append(entry_id)

        for entry_id in to_delete:
            del self._entries[entry_id]

        if to_delete:
            self._save_entries()

        return len(to_delete)
