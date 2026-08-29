"""Website policy for Bahram Agent."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class WebsiteRule:
    """A website access rule."""

    pattern: str
    action: str  # "allow", "deny", "log"
    reason: str = ""


class WebsitePolicy:
    """Manage website access policies."""

    def __init__(self) -> None:
        self._rules: list[WebsiteRule] = []
        self._default_action = "allow"
        self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default rules."""
        self._rules = [
            # Deny dangerous sites
            WebsiteRule(pattern="*.malware.com", action="deny", reason="Malware site"),
            WebsiteRule(pattern="*.phishing.com", action="deny", reason="Phishing site"),
            # Allow common dev sites
            WebsiteRule(pattern="github.com", action="allow"),
            WebsiteRule(pattern="stackoverflow.com", action="allow"),
            WebsiteRule(pattern="docs.python.org", action="allow"),
            # Log analytics
            WebsiteRule(pattern="*", action="log", reason="Default logging"),
        ]

    def check_url(self, url: str) -> tuple[str, str]:
        """Check if a URL is allowed.

        Returns:
            Tuple of (action, reason)
        """
        url_lower = url.lower()

        for rule in self._rules:
            pattern = rule.pattern.lower()

            # Simple wildcard matching
            if pattern.startswith("*."):
                domain = pattern[2:]
                if url_lower.endswith(domain) or domain in url_lower:
                    return rule.action, rule.reason
            elif pattern in url_lower:
                return rule.action, rule.reason

        return self._default_action, "Default policy"

    def add_rule(self, rule: WebsiteRule) -> None:
        """Add a rule."""
        self._rules.insert(0, rule)  # Insert at beginning for priority

    def remove_rule(self, pattern: str) -> bool:
        """Remove a rule by pattern."""
        for i, rule in enumerate(self._rules):
            if rule.pattern == pattern:
                del self._rules[i]
                return True
        return False

    def set_default_action(self, action: str) -> None:
        """Set default action."""
        self._default_action = action

    def list_rules(self) -> list[dict]:
        """List all rules."""
        return [
            {"pattern": r.pattern, "action": r.action, "reason": r.reason}
            for r in self._rules
        ]
