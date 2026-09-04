"""
Website policy.

Public objects: ``WebsiteRule``, ``WebsitePolicy``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WebsiteRule:
    """
    Website rule.

    Attributes:
        pattern (str): pattern string.
        action (str): action string.
        reason (str): reason string.
    """

    pattern: str
    action: str
    reason: str = ""


class WebsitePolicy:
    """
    Website policy.
    """

    def __init__(self) -> None:
        """
        Initialise a WebsitePolicy instance.
        """
        self._rules: list[WebsiteRule] = []
        self._default_action = "allow"
        self._load_defaults()

    def _load_defaults(self) -> None:
        self._rules = [
            WebsiteRule(pattern="*.malware.com", action="deny", reason="Malware site"),
            WebsiteRule(pattern="*.phishing.com", action="deny", reason="Phishing site"),
            WebsiteRule(pattern="github.com", action="allow"),
            WebsiteRule(pattern="stackoverflow.com", action="allow"),
            WebsiteRule(pattern="docs.python.org", action="allow"),
            WebsiteRule(pattern="*", action="log", reason="Default logging"),
        ]

    def check_url(self, url: str) -> tuple[str, str]:
        """
        Check url.

        Args:
            url (str): url string.

        Returns:
            tuple[str, str]: a sequence of str, str entries (empty when there is nothing to report).
        """
        url_lower = url.lower()

        for rule in self._rules:
            pattern = rule.pattern.lower()

            if pattern.startswith("*."):
                domain = pattern[2:]
                if url_lower.endswith(domain) or domain in url_lower:
                    return rule.action, rule.reason
            elif pattern in url_lower:
                return rule.action, rule.reason

        return self._default_action, "Default policy"

    def add_rule(self, rule: WebsiteRule) -> None:
        """
        Add rule.

        Args:
            rule (WebsiteRule): rule.
        """
        self._rules.insert(0, rule)

    def remove_rule(self, pattern: str) -> bool:
        """
        Remove rule.

        Args:
            pattern (str): pattern string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        for i, rule in enumerate(self._rules):
            if rule.pattern == pattern:
                del self._rules[i]
                return True
        return False

    def set_default_action(self, action: str) -> None:
        """
        Set the default action.

        Args:
            action (str): action string.
        """
        self._default_action = action

    def list_rules(self) -> list[dict]:
        """
        List rules.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
        return [{"pattern": r.pattern, "action": r.action, "reason": r.reason} for r in self._rules]
