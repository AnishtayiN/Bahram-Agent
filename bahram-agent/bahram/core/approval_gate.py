from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)

@dataclass
class ApprovalGate:
    ""

    name: str
    pattern: str
    description: str
    require_approval: bool = True
    auto_approve: bool = False
    approver: str = ""

class ApprovalGateManager:
    ""

    def __init__(self, data_dir: str = "data/security") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._gates: list[ApprovalGate] = []
        self._pending: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        ""

        self._gates = [
            ApprovalGate(
                name="critical_files",
                pattern="**/*.py",
                description="Python source files",
                require_approval=False,
            ),
            ApprovalGate(
                name="config_files",
                pattern="**/*.yaml,*.json,*.toml",
                description="Configuration files",
                require_approval=True,
            ),
            ApprovalGate(
                name="secret_files",
                pattern="**/*.env,*.key,*.pem",
                description="Secret files",
                require_approval=True,
            ),
            ApprovalGate(
                name="system_files",
                pattern="/etc/*,/usr/*",
                description="System files",
                require_approval=True,
            ),
        ]

    def check_write(self, file_path: str) -> tuple[bool, str]:
        ""
        path = Path(file_path)

        for gate in self._gates:
            if not gate.require_approval:
                continue

            if self._matches_pattern(path, gate.pattern):
                if gate.auto_approve:
                    return False, "Auto-approved"

                return True, f"Requires approval: {gate.description}"

        return False, "No approval required"

    def _matches_pattern(self, path: Path, pattern: str) -> bool:
        ""
        path_str = str(path)
        patterns = [p.strip() for p in pattern.split(",")]

        for p in patterns:
            if p.startswith("**/"):

                suffix = p[3:]
                if path_str.endswith(suffix) or path.match(p):
                    return True
            elif p.startswith("/"):

                if path_str.startswith(p):
                    return True
            else:

                if path_str.endswith(p):
                    return True

        return False

    def request_approval(self, write_id: str, file_path: str, reason: str) -> dict:
        ""
        self._pending[write_id] = {
            "file_path": file_path,
            "reason": reason,
            "status": "pending",
        }
        return self._pending[write_id]

    def approve(self, write_id: str) -> bool:
        ""
        if write_id in self._pending:
            self._pending[write_id]["status"] = "approved"
            return True
        return False

    def deny(self, write_id: str) -> bool:
        ""
        if write_id in self._pending:
            self._pending[write_id]["status"] = "denied"
            return True
        return False

    def get_pending(self) -> list[dict]:
        ""
        return [
            {"id": k, **v}
            for k, v in self._pending.items()
            if v["status"] == "pending"
        ]

    def add_gate(self, gate: ApprovalGate) -> None:
        ""
        self._gates.append(gate)
