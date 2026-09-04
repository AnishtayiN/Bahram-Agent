from __future__ import annotations

import json
import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class Checkpoint:

    id: str
    name: str
    timestamp: float
    description: str
    files: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

class CheckpointManager:

    def __init__(self, data_dir: str = "data/checkpoints", max_checkpoints: int = 10) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._max_checkpoints = max_checkpoints
        self._checkpoints: list[Checkpoint] = []
        self._snapshots_dir = self.data_dir / "snapshots"
        self._snapshots_dir.mkdir(exist_ok=True)
        self._load()

    def _load(self) -> None:
        checkpoints_file = self.data_dir / "checkpoints.json"
        if checkpoints_file.exists():
            try:
                with open(checkpoints_file) as f:
                    data = json.load(f)
                self._checkpoints = [Checkpoint(**c) for c in data]
            except Exception as e:
                logger.warning(f"Failed to load checkpoints: {e}")

    def _save(self) -> None:
        checkpoints_file = self.data_dir / "checkpoints.json"
        data = [
            {
                "id": c.id,
                "name": c.name,
                "timestamp": c.timestamp,
                "description": c.description,
                "files": c.files,
                "metadata": c.metadata,
            }
            for c in self._checkpoints
        ]
        with open(checkpoints_file, "w") as f:
            json.dump(data, f, indent=2)

    def create_checkpoint(
        self,
        name: str,
        files: list[str],
        description: str = "",
        metadata: dict = None,
    ) -> Checkpoint:
        checkpoint_id = f"cp_{int(time.time() * 1000)}"
        snapshot_dir = self._snapshots_dir / checkpoint_id
        snapshot_dir.mkdir(exist_ok=True)

        copied_files = []
        for file_path in files:
            src = Path(file_path)
            if src.exists():
                dst = snapshot_dir / src.name
                if src.is_file():
                    shutil.copy2(src, dst)
                    copied_files.append(str(src))
                elif src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                    copied_files.append(str(src))

        checkpoint = Checkpoint(
            id=checkpoint_id,
            name=name,
            timestamp=time.time(),
            description=description,
            files=copied_files,
            metadata=metadata or {},
        )

        self._checkpoints.append(checkpoint)

        if len(self._checkpoints) > self._max_checkpoints:
            removed = self._checkpoints[: len(self._checkpoints) - self._max_checkpoints]
            for old in removed:
                old_snapshot = self._snapshots_dir / old.id
                if old_snapshot.exists():
                    shutil.rmtree(old_snapshot)
            self._checkpoints = self._checkpoints[-self._max_checkpoints:]

        self._save()
        return checkpoint

    def rollback(self, checkpoint_id: str) -> bool:
        checkpoint = next(
            (c for c in self._checkpoints if c.id == checkpoint_id), None
        )
        if not checkpoint:
            return False

        snapshot_dir = self._snapshots_dir / checkpoint_id
        if not snapshot_dir.exists():
            return False

        for file_path in checkpoint.files:
            src = Path(file_path)
            snapshot_file = snapshot_dir / src.name
            if snapshot_file.exists():
                if snapshot_file.is_file():
                    shutil.copy2(snapshot_file, src)
                elif snapshot_file.is_dir():
                    shutil.copytree(snapshot_file, src, dirs_exist_ok=True)

        return True

    def list_checkpoints(self) -> list[dict]:
        return [
            {
                "id": c.id,
                "name": c.name,
                "timestamp": c.timestamp,
                "description": c.description,
                "file_count": len(c.files),
            }
            for c in self._checkpoints
        ]

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        checkpoint = next(
            (c for c in self._checkpoints if c.id == checkpoint_id), None
        )
        if not checkpoint:
            return False

        snapshot_dir = self._snapshots_dir / checkpoint_id
        if snapshot_dir.exists():
            shutil.rmtree(snapshot_dir)

        self._checkpoints.remove(checkpoint)
        self._save()
        return True
