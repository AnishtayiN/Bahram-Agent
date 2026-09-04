"""
Delivery.

Public objects: ``DeliveryEntry``, ``DeliveryLedger``.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DeliveryEntry:
    """
    Delivery entry.

    Attributes:
        message_id (str): message id string.
        platform (str): platform string.
        chat_id (str): chat id string.
        content (str): text content to process.
        status (str): status string.
        timestamp (float): numeric value for timestamp.
        attempts (int): numeric value for attempts.
        max_attempts (int): numeric value for max attempts.
        error (str): error string.
    """

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
    """
    Delivery ledger.
    """

    def __init__(self, data_dir: str = "data/gateway") -> None:
        """
        Initialise a DeliveryLedger instance.

        Args:
            data_dir (str): directory that holds the on-disk state. Defaults to ``'data/gateway'``.
        """
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
        """
        Record send.

        Args:
            message_id (str): message id string.
            platform (str): platform string.
            chat_id (str): chat id string.
            content (str): text content to process.

        Returns:
            DeliveryEntry: the resulting DeliveryEntry.
        """
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
        """
        Mark sent.

        Args:
            message_id (str): message id string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        if message_id in self._entries:
            self._entries[message_id].status = "sent"
            self._save()
            return True
        return False

    def mark_failed(self, message_id: str, error: str) -> bool:
        """
        Mark failed.

        Args:
            message_id (str): message id string.
            error (str): error string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
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
        """
        Return the pending.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
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
        """
        Return the retryable.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
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
        """
        Cleanup.

        Args:
            max_age_seconds (int): numeric value for max age seconds. Defaults to ``86400``.

        Returns:
            int: the computed numeric value.
        """
        now = time.time()
        to_remove = [
            msg_id
            for msg_id, entry in self._entries.items()
            if entry.status in ("sent", "failed") and (now - entry.timestamp) > max_age_seconds
        ]
        for msg_id in to_remove:
            del self._entries[msg_id]
        if to_remove:
            self._save()
        return len(to_remove)
