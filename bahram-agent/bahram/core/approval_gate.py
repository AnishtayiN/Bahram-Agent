"""Write approval gates for Bahram Agent."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class PendingWrite:
    """A pending write waiting for approval."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str = ""  # memory, skill
    action: str = ""  # create, edit, patch, delete
    target: str = ""
    content: str = ""
    old_content: str = ""
    status: str = "pending"  # pending, approved, rejected
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class WriteApprovalGate:
    """Gate memory/skill writes for approval."""

    def __init__(self, data_dir: str = "data/pending") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._pending: dict[str, PendingWrite] = {}
        self._memory_enabled = True
        self._skill_enabled = True
        self._load_pending()

    def _load_pending(self) -> None:
        """Load pending writes."""
        pending_file = self.data_dir / "pending.json"
        if pending_file.exists():
            try:
                with open(pending_file) as f:
                    data = json.load(f)
                for item in data:
                    pw = PendingWrite(**item)
                    self._pending[pw.id] = pw
            except Exception as e:
                logger.warning(f"Failed to load pending: {e}")

    def _save_pending(self) -> None:
        """Save pending writes."""
        pending_file = self.data_dir / "pending.json"
        data = [
            {
                "id": pw.id,
                "type": pw.type,
                "action": pw.action,
                "target": pw.target,
                "content": pw.content,
                "old_content": pw.old_content,
                "status": pw.status,
                "created_at": pw.created_at,
            }
            for pw in self._pending.values()
        ]
        with open(pending_file, "w") as f:
            json.dump(data, f, indent=2)

    def stage_write(
        self,
        write_type: str,
        action: str,
        target: str,
        content: str = "",
        old_content: str = "",
    ) -> PendingWrite:
        """Stage a write for approval."""
        pw = PendingWrite(
            type=write_type,
            action=action,
            target=target,
            content=content,
            old_content=old_content,
        )
        self._pending[pw.id] = pw
        self._save_pending()
        return pw

    def approve_write(self, write_id: str) -> Optional[PendingWrite]:
        """Approve a pending write."""
        pw = self._pending.get(write_id)
        if pw:
            pw.status = "approved"
            self._save_pending()
            return pw
        return None

    def reject_write(self, write_id: str) -> Optional[PendingWrite]:
        """Reject a pending write."""
        pw = self._pending.get(write_id)
        if pw:
            pw.status = "rejected"
            self._save_pending()
            return pw
        return None

    def approve_all(self) -> int:
        """Approve all pending writes."""
        count = 0
        for pw in self._pending.values():
            if pw.status == "pending":
                pw.status = "approved"
                count += 1
        self._save_pending()
        return count

    def reject_all(self) -> int:
        """Reject all pending writes."""
        count = 0
        for pw in self._pending.values():
            if pw.status == "pending":
                pw.status = "rejected"
                count += 1
        self._save_pending()
        return count

    def get_pending(self) -> list[PendingWrite]:
        """Get all pending writes."""
        return [pw for pw in self._pending.values() if pw.status == "pending"]

    def set_memory_approval(self, enabled: bool) -> None:
        """Enable/disable memory write approval."""
        self._memory_enabled = enabled

    def set_skill_approval(self, enabled: bool) -> None:
        """Enable/disable skill write approval."""
        self._skill_enabled = enabled

    def needs_approval(self, write_type: str) -> bool:
        """Check if writes of this type need approval."""
        if write_type == "memory":
            return self._memory_enabled
        if write_type == "skill":
            return self._skill_enabled
        return False

    def render_pending(self) -> str:
        """Render pending writes."""
        pending = self.get_pending()
        if not pending:
            return "No pending writes."

        parts = []
        for pw in pending:
            parts.append(f"[{pw.id}] {pw.type}/{pw.action}: {pw.target}")
        return "\n".join(parts)
