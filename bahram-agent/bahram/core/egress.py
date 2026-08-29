"""Egress proxy for Bahram Agent."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class EgressProxyConfig:
    """Egress proxy configuration."""

    enabled: bool = False
    http_proxy: str = ""
    https_proxy: str = ""
    no_proxy: str = "localhost,127.0.0.1"
    socks5_proxy: str = ""


class EgressProxy:
    """Manage egress proxy settings."""

    def __init__(self, config: EgressProxyConfig = None) -> None:
        self.config = config or EgressProxyConfig()

    def get_proxy_env(self) -> dict[str, str]:
        """Get proxy environment variables."""
        if not self.config.enabled:
            return {}

        env = {}
        if self.config.http_proxy:
            env["HTTP_PROXY"] = self.config.http_proxy
        if self.config.https_proxy:
            env["HTTPS_PROXY"] = self.config.https_proxy
        if self.config.no_proxy:
            env["NO_PROXY"] = self.config.no_proxy
        if self.config.socks5_proxy:
            env["ALL_PROXY"] = self.config.socks5_proxy
        return env

    def get_httpx_kwargs(self) -> dict:
        """Get kwargs for httpx client."""
        if not self.config.enabled:
            return {}

        kwargs = {}
        if self.config.https_proxy:
            kwargs["proxy"] = self.config.https_proxy
        elif self.config.http_proxy:
            kwargs["proxy"] = self.config.http_proxy
        return kwargs

    def should_proxy(self, url: str) -> bool:
        """Check if URL should use proxy."""
        if not self.config.enabled:
            return False

        # Check no_proxy
        for host in self.config.no_proxy.split(","):
            host = host.strip()
            if host and host in url:
                return False
        return True
