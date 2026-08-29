"""Checkpoints and rollback for Bahram Agent."""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Checkpoint:
    """A filesystem checkpoint."""

    id: str
    path: str
    description: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    files: list[str] = field(default_factory=list)


class CheckpointManager:
    """Create and manage filesystem checkpoints."""

    def __init__(self, data_dir: str = "data/checkpoints") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoints: dict[str, Checkpoint] = {}
        self._load_checkpoints()

    def _load_checkpoints(self) -> None:
        """Load checkpoints from disk."""
        for cp_file in self.data_dir.glob("*.json"):
            try:
                with open(cp_file) as f:
                    data = json.load(f)
                cp = Checkpoint(**data)
                self._checkpoints[cp.id] = cp
            except Exception as e:
                logger.warning(f"Failed to load checkpoint {cp_file}: {e}")

    def create_checkpoint(
        self,
        path: str,
        description: str = "",
    ) -> Checkpoint:
        """Create a checkpoint of a directory."""
        import uuid

        cp_id = str(uuid.uuid4())[:8]
        cp_dir = self.data_dir / cp_id
        cp_dir.mkdir(parents=True, exist_ok=True)

        # Copy files
        source = Path(path)
        files = []
        if source.exists():
            if source.is_dir():
                shutil.copytree(source, cp_dir / "files", dirs_exist_ok=True)
                files = [str(f.relative_to(source)) for f in source.rglob("*") if f.is_file()]
            else:
                shutil.copy2(source, cp_dir / "files")
                files = [source.name]

        cp = Checkpoint(
            id=cp_id,
            path=path,
            description=description,
            files=files,
        )
        self._checkpoints[cp_id] = cp

        # Save metadata
        meta_file = self.data_dir / f"{cp_id}.json"
        with open(meta_file, "w") as f:
            json.dump({
                "id": cp.id,
                "path": cp.path,
                "description": cp.description,
                "created_at": cp.created_at,
                "files": cp.files,
            }, f, indent=2)

        return cp

    def restore_checkpoint(self, cp_id: str) -> bool:
        """Restore a checkpoint."""
        cp = self._checkpoints.get(cp_id)
        if not cp:
            return False

        cp_dir = self.data_dir / cp_id / "files"
        if not cp_dir.exists():
            return False

        target = Path(cp.path)
        if target.is_dir():
            shutil.copytree(cp_dir, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cp_dir, target)

        return True

    def list_checkpoints(self) -> list[Checkpoint]:
        """List all checkpoints."""
        return list(self._checkpoints.values())

    def delete_checkpoint(self, cp_id: str) -> bool:
        """Delete a checkpoint."""
        if cp_id in self._checkpoints:
            cp_dir = self.data_dir / cp_id
            shutil.rmtree(cp_dir, ignore_errors=True)
            meta_file = self.data_dir / f"{cp_id}.json"
            meta_file.unlink(missing_ok=True)
            del self._checkpoints[cp_id]
            return True
        return False
