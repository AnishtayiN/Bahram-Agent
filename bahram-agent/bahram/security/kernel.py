from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Capability:
    name: str
    scope: str = "global"
    resources: list[str] = field(default_factory=list)
    max_risk: str = "medium"
    expires_at: float | None = None
    one_time: bool = False


@dataclass
class AuthorizationRequest:
    request_id: str
    identity: str
    capability: str
    resource: str
    risk_level: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class AuthorizationResult:
    granted: bool
    reason: str
    authorization_id: str = ""
    scope: str = ""
    expires_at: float | None = None


class SecurityKernel:
    def __init__(self) -> None:
        self._capabilities: dict[str, list[Capability]] = {}
        self._authorizations: dict[str, AuthorizationResult] = {}
        self._denied: list[dict[str, Any]] = []
        self._initialize_default_capabilities()

    def _initialize_default_capabilities(self) -> None:
        self.grant_capability("system", Capability(
            name="file_read", scope="workspace", max_risk="low",
        ))
        self.grant_capability("system", Capability(
            name="file_write", scope="workspace", max_risk="medium",
        ))
        self.grant_capability("system", Capability(
            name="execute", scope="workspace", max_risk="high",
        ))
        self.grant_capability("system", Capability(
            name="network", scope="global", max_risk="medium",
        ))
        self.grant_capability("system", Capability(
            name="memory_read", scope="session", max_risk="low",
        ))
        self.grant_capability("system", Capability(
            name="memory_write", scope="session", max_risk="medium",
        ))

    def grant_capability(self, identity: str, capability: Capability) -> None:
        if identity not in self._capabilities:
            self._capabilities[identity] = []
        self._capabilities[identity].append(capability)

    def revoke_capability(self, identity: str, capability_name: str) -> bool:
        if identity not in self._capabilities:
            return False
        before = len(self._capabilities[identity])
        self._capabilities[identity] = [
            c for c in self._capabilities[identity] if c.name != capability_name
        ]
        return len(self._capabilities[identity]) < before

    def check_authorization(self, request: AuthorizationRequest) -> AuthorizationResult:
        now = time.time()
        caps = self._capabilities.get(request.identity, [])
        for cap in caps:
            if cap.expires_at and now > cap.expires_at:
                continue
            if cap.name == request.capability:
                risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
                if risk_order.get(request.risk_level, 0) <= risk_order.get(cap.max_risk, 2):
                    result = AuthorizationResult(
                        granted=True, reason="capability matched",
                        authorization_id=f"auth_{int(now * 1000)}",
                        scope=cap.scope, expires_at=cap.expires_at,
                    )
                    self._authorizations[result.authorization_id] = result
                    if cap.one_time:
                        self.revoke_capability(request.identity, cap.name)
                    return result
        result = AuthorizationResult(
            granted=False,
            reason=f"no capability '{request.capability}' for identity '{request.identity}'",
        )
        self._denied.append({
            "request": request, "result": result, "timestamp": now,
        })
        logger.warning(f"Authorization denied: {result.reason}")
        return result

    def check_child_capability(self, parent_identity: str, child_identity: str, capability: str) -> bool:
        parent_caps = self._capabilities.get(parent_identity, [])
        child_caps = self._capabilities.get(child_identity, [])
        parent_names = {c.name for c in parent_caps}
        child_names = {c.name for c in child_caps}
        return child_names.issubset(parent_names) or capability in parent_names

    def enforce_child_scope(self, parent_identity: str, child_identity: str) -> None:
        parent_caps = self._capabilities.get(parent_identity, [])
        child_caps = []
        for cap in parent_caps:
            child_caps.append(Capability(
                name=cap.name,
                scope=cap.scope,
                resources=list(cap.resources),
                max_risk=cap.max_risk,
                expires_at=cap.expires_at,
                one_time=cap.one_time,
            ))
        self._capabilities[child_identity] = child_caps

    def get_audit_log(self) -> list[dict[str, Any]]:
        return [
            {"type": "denied", "timestamp": d["timestamp"],
             "identity": d["request"].identity, "capability": d["request"].capability,
             "reason": d["result"].reason}
            for d in self._denied[-100:]
        ]
