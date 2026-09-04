from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolRoute:
    tool_name: str
    capability: str
    risk_level: str
    timeout_seconds: float = 120.0
    requires_approval: bool = False
    provider: str = ""
    reason: str = ""


@dataclass
class ToolSearchResult:
    tool_name: str
    score: float
    route: ToolRoute
    reason: str = ""


class ToolGateway:
    def __init__(self, tools: dict[str, Any], approval_system: Any = None) -> None:
        self.tools = tools
        self.approval_system = approval_system
        self._routes: dict[str, ToolRoute] = {}
        self._risk_map: dict[str, str] = {}
        self._initialize_routes()

    def _initialize_routes(self) -> None:
        for name, tool in self.tools.items():
            risk = "low"
            capability = "general"
            requires_approval = False
            if hasattr(tool, 'description'):
                desc = tool.description.lower()
                if any(kw in desc for kw in ["bash", "shell", "execute", "command"]):
                    risk = "high"
                    capability = "execution"
                    requires_approval = True
                elif any(kw in desc for kw in ["write", "edit", "create", "delete"]):
                    risk = "medium"
                    capability = "file_mutate"
                    requires_approval = True
                elif any(kw in desc for kw in ["read", "search", "fetch"]):
                    risk = "low"
                    capability = "file_read"
                elif any(kw in desc for kw in ["git"]):
                    risk = "medium"
                    capability = "vcs"
                    requires_approval = True
            self._routes[name] = ToolRoute(
                tool_name=name, capability=capability, risk_level=risk,
                requires_approval=requires_approval,
            )

    def search_tools(self, task: str, context: dict[str, Any] | None = None) -> list[ToolSearchResult]:
        task_lower = task.lower()
        results = []
        for name, route in self._routes.items():
            score = 0.0
            reason = ""
            if hasattr(self.tools[name], 'description'):
                desc = self.tools[name].description.lower()
                words = set(task_lower.split())
                desc_words = set(desc.split())
                overlap = words & desc_words
                if overlap:
                    score = len(overlap) / max(len(words), 1)
                    reason = f"matched: {', '.join(list(overlap)[:3])}"
            if score > 0:
                results.append(ToolSearchResult(
                    tool_name=name, score=score, route=route, reason=reason,
                ))
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:10]

    def get_route(self, tool_name: str) -> ToolRoute | None:
        return self._routes.get(tool_name)

    def filter_by_capability(self, capability: str) -> list[str]:
        return [name for name, route in self._routes.items() if route.capability == capability]

    def filter_by_risk(self, max_risk: str) -> list[str]:
        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        max_level = risk_order.get(max_risk, 2)
        return [
            name for name, route in self._routes.items()
            if risk_order.get(route.risk_level, 0) <= max_level
        ]

    def get_tools_for_context(self, task: str, allowed_risk: str = "medium") -> list[str]:
        candidates = self.filter_by_risk(allowed_risk)
        results = self.search_tools(task)
        result_names = {r.tool_name for r in results}
        return [n for n in candidates if n in result_names] or candidates[:5]
