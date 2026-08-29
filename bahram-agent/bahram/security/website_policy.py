"""Website access policy for Bahram Agent."""

from __future__ import annotations

import fnmatch
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class WebsitePolicy:
    """Website access policy configuration."""

    enabled: bool = False
    blocklist: list[str] = field(default_factory=list)
    allowlist: list[str] = field(default_factory=list)
    shared_files: list[str] = field(default_factory=list)


class WebsiteAccessPolicy:
    """Enforce website access policies."""

    def __init__(self, policy: WebsitePolicy = None) -> None:
        self.policy = policy or WebsitePolicy()

    def is_allowed(self, url: str) -> tuple[bool, str]:
        """Check if URL is allowed.

        Returns:
            Tuple of (is_allowed, reason)
        """
        if not self.policy.enabled:
            return True, ""

        # Extract domain from URL
        domain = self._extract_domain(url)

        # Check allowlist first (if configured)
        if self.policy.allowlist:
            for pattern in self.policy.allowlist:
                if fnmatch.fnmatch(domain, pattern):
                    return True, "allowed by allowlist"
            return False, "not in allowlist"

        # Check blocklist
        for pattern in self.policy.blocklist:
            if fnmatch.fnmatch(domain, pattern):
                return False, f"blocked by policy: {pattern}"

        return True, ""

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        domain = url.split("://")[-1].split("/")[0].split("?")[0]
        return domain.lower()

    def add_to_blocklist(self, pattern: str) -> None:
        """Add a pattern to the blocklist."""
        if pattern not in self.policy.blocklist:
            self.policy.blocklist.append(pattern)

    def remove_from_blocklist(self, pattern: str) -> bool:
        """Remove a pattern from the blocklist."""
        if pattern in self.policy.blocklist:
            self.policy.blocklist.remove(pattern)
            return True
        return False

    def load_shared_blocklist(self, filepath: str) -> None:
        """Load blocklist from a shared file."""
        try:
            from pathlib import Path
            content = Path(filepath).read_text(encoding="utf-8")
            for line in content.strip().split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    if line not in self.policy.blocklist:
                        self.policy.blocklist.append(line)
        except Exception as e:
            logger.warning(f"Failed to load shared blocklist: {e}")
