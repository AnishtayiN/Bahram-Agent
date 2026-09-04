from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class DeliveryEntry:

    message_id: str
    platform: str
    chat_id: str
    content: str
    status: str
    timestamp: float
    attempts: int = 0
    max_attempts: int = 3
    error: str = ""

class DeliveryLedger:

    def __init__(self, data_dir: str = "data/gateway") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, DeliveryEntry] = {}
        self._load()

    def _load(self) -> None:
        ledger_file = self.data_dir / "delivery_ledger.json"
        if ledger_file.exists():
            try:
                with open(ledger_file) as f:
                    data = json.load(f)
                for entry_data in data:
                    entry = DeliveryEntry(**entry_data)
                    self._entries[entry.message_id] = entry
            except Exception as e:
                logger.warning(f"Failed to load delivery ledger: {e}")

    def _save(self) -> None:
        ledger_file = self.data_dir / "delivery_ledger.json"
        data = [
            {
                "message_id": e.message_id,
                "platform": e.platform,
                "chat_id": e.chat_id,
                "content": e.content,
                "status": e.status,
                "timestamp": e.timestamp,
                "attempts": e.attempts,
                "max_attempts": e.max_attempts,
                "error": e.error,
            }
            for e in self._entries.values()
        ]
        with open(ledger_file, "w") as f:
            json.dump(data, f, indent=2)

    def record_send(
        self,
        message_id: str,
        platform: str,
        chat_id: str,
        content: str,
    ) -> DeliveryEntry:
        entry = DeliveryEntry(
            message_id=message_id,
            platform=platform,
            chat_id=chat_id,
            content=content,
            status="pending",
            timestamp=time.time(),
        )
        self._entries[message_id] = entry
        self._save()
        return entry

    def mark_sent(self, message_id: str) -> bool:
        if message_id in self._entries:
            self._entries[message_id].status = "sent"
            self._save()
            return True
        return False

    def mark_failed(self, message_id: str, error: str) -> bool:
        if message_id in self._entries:
            entry = self._entries[message_id]
            entry.attempts += 1
            entry.error = error
            if entry.attempts >= entry.max_attempts:
                entry.status = "failed"
            self._save()
            return True
        return False

    def get_pending(self) -> list[dict]:
        return [
            {
                "message_id": e.message_id,
                "platform": e.platform,
                "chat_id": e.chat_id,
                "content": e.content[:100],
                "attempts": e.attempts,
            }
            for e in self._entries.values()
            if e.status == "pending"
        ]

    def get_retryable(self) -> list[dict]:
        return [
            {
                "message_id": e.message_id,
                "platform": e.platform,
                "chat_id": e.chat_id,
                "content": e.content,
            }
            for e in self._entries.values()
            if e.status == "pending" and e.attempts < e.max_attempts
        ]

    def cleanup(self, max_age_seconds: int = 86400) -> int:
        now = time.time()
        to_remove = [
            msg_id
            for msg_id, entry in self._entries.items()
            if entry.status in ("sent", "failed")
            and (now - entry.timestamp) > max_age_seconds
        ]
        for msg_id in to_remove:
            del self._entries[msg_id]
        if to_remove:
            self._save()
        return len(to_remove)
