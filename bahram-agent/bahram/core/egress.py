"""
Egress.

Public objects: ``EgressProxy``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class EgressProxy:
    """
    Egress proxy.
    """

    def __init__(self) -> None:
        """
        Initialise a EgressProxy instance.
        """
        self._proxy_url: str = ""
        self._proxy_type: str = "http"
        self._no_proxy: list[str] = []
        self._load()

    def _load(self) -> None:
        self._proxy_url = os.environ.get("BAHRAM_PROXY", "")
        self._proxy_type = os.environ.get("BAHRAM_PROXY_TYPE", "http")

        no_proxy = os.environ.get("NO_PROXY", "")
        if no_proxy:
            self._no_proxy = [h.strip() for h in no_proxy.split(",")]

    def set_proxy(self, url: str, proxy_type: str = "http") -> None:
        """
        Set the proxy.

        Args:
            url (str): url string.
            proxy_type (str): proxy type string. Defaults to ``'http'``.
        """
        self._proxy_url = url
        self._proxy_type = proxy_type

    def get_proxy(self) -> str | None:
        """
        Return the proxy.

        Returns:
            str | None: the resulting object, or ``None`` when it is not available.
        """
        return self._proxy_url or None

    def should_proxy(self, hostname: str) -> bool:
        """
        Return ``True`` when proxy.

        Args:
            hostname (str): hostname string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        if not self._proxy_url:
            return False

        for pattern in self._no_proxy:
            if pattern.startswith("."):
                if hostname.endswith(pattern) or hostname == pattern[1:]:
                    return False
            elif pattern == "*":
                return False
            elif hostname == pattern:
                return False

        return True

    def get_httpx_proxy(self) -> str | None:
        """
        Return the httpx proxy.

        Returns:
            str | None: the resulting object, or ``None`` when it is not available.
        """
        if not self._proxy_url:
            return None

        if self._proxy_type == "socks5":
            return f"socks5://{self._proxy_url}"
        return self._proxy_url

    def get_env(self) -> dict[str, str]:
        """
        Return the env.

        Returns:
            dict[str, str]: a mapping of str, str.
        """
        if not self._proxy_url:
            return {}

        return {
            "HTTP_PROXY": self._proxy_url,
            "HTTPS_PROXY": self._proxy_url,
            "NO_PROXY": ",".join(self._no_proxy),
        }

    def add_no_proxy(self, hostname: str) -> None:
        """
        Add no proxy.

        Args:
            hostname (str): hostname string.
        """
        if hostname not in self._no_proxy:
            self._no_proxy.append(hostname)

    def remove_no_proxy(self, hostname: str) -> bool:
        """
        Remove no proxy.

        Args:
            hostname (str): hostname string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        if hostname in self._no_proxy:
            self._no_proxy.remove(hostname)
            return True
        return False

    def get_config(self) -> dict[str, Any]:
        """
        Return the config.

        Returns:
            dict[str, Any]: a mapping of str, Any.
        """
        return {
            "proxy_url": self._proxy_url,
            "proxy_type": self._proxy_type,
            "no_proxy": self._no_proxy,
            "enabled": bool(self._proxy_url),
        }
