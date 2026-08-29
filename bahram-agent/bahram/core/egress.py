"""Egress proxy for Bahram Agent."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EgressProxy:
    """Manage network egress proxy."""

    def __init__(self) -> None:
        self._proxy_url: str = ""
        self._proxy_type: str = "http"  # http, socks5
        self._no_proxy: list[str] = []
        self._load()

    def _load(self) -> None:
        """Load proxy config from environment."""
        self._proxy_url = os.environ.get("BAHRAM_PROXY", "")
        self._proxy_type = os.environ.get("BAHRAM_PROXY_TYPE", "http")

        no_proxy = os.environ.get("NO_PROXY", "")
        if no_proxy:
            self._no_proxy = [h.strip() for h in no_proxy.split(",")]

    def set_proxy(self, url: str, proxy_type: str = "http") -> None:
        """Set proxy URL."""
        self._proxy_url = url
        self._proxy_type = proxy_type

    def get_proxy(self) -> Optional[str]:
        """Get proxy URL."""
        return self._proxy_url or None

    def should_proxy(self, hostname: str) -> bool:
        """Check if a hostname should be proxied."""
        if not self._proxy_url:
            return False

        # Check no-proxy list
        for pattern in self._no_proxy:
            if pattern.startswith("."):
                # Domain suffix
                if hostname.endswith(pattern) or hostname == pattern[1:]:
                    return False
            elif pattern == "*":
                return False
            elif hostname == pattern:
                return False

        return True

    def get_httpx_proxy(self) -> Optional[str]:
        """Get proxy URL for httpx."""
        if not self._proxy_url:
            return None

        if self._proxy_type == "socks5":
            return f"socks5://{self._proxy_url}"
        return self._proxy_url

    def get_env(self) -> dict[str, str]:
        """Get proxy environment variables."""
        if not self._proxy_url:
            return {}

        return {
            "HTTP_PROXY": self._proxy_url,
            "HTTPS_PROXY": self._proxy_url,
            "NO_PROXY": ",".join(self._no_proxy),
        }

    def add_no_proxy(self, hostname: str) -> None:
        """Add hostname to no-proxy list."""
        if hostname not in self._no_proxy:
            self._no_proxy.append(hostname)

    def remove_no_proxy(self, hostname: str) -> bool:
        """Remove hostname from no-proxy list."""
        if hostname in self._no_proxy:
            self._no_proxy.remove(hostname)
            return True
        return False

    def get_config(self) -> dict[str, Any]:
        """Get proxy configuration."""
        return {
            "proxy_url": self._proxy_url,
            "proxy_type": self._proxy_type,
            "no_proxy": self._no_proxy,
            "enabled": bool(self._proxy_url),
        }
