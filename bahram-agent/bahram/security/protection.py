"""Security system for Bahram Agent."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SSRFProtector:
    """SSRF protection for URL-capable tools."""

    BLOCKED_RANGES = [
        ("10.0.0.0", "10.255.255.255"),      # RFC 1918
        ("172.16.0.0", "172.31.255.255"),     # RFC 1918
        ("192.168.0.0", "192.168.255.255"),   # RFC 1918
        ("127.0.0.0", "127.255.255.255"),     # Loopback
        ("169.254.0.0", "169.254.255.255"),   # Link-local / cloud metadata
        ("100.64.0.0", "100.127.255.255"),    # CGNAT
    ]

    BLOCKED_HOSTNAMES = [
        "metadata.google.internal",
        "metadata.goog",
        "169.254.169.254",
    ]

    BLOCKED_IP_PREFIXES = [
        "fe80:",     # IPv6 link-local
        "fc00:",     # IPv6 unique local
        "fd00:",     # IPv6 unique local
        "::1",       # IPv6 loopback
    ]

    def __init__(self, allow_private: bool = False) -> None:
        self.allow_private = allow_private

    def check_url(self, url: str) -> tuple[bool, str]:
        """Check if URL is safe to fetch.

        Returns:
            Tuple of (is_safe, reason)
        """
        if self.allow_private:
            return True, ""

        # Check hostname
        hostname = self._extract_hostname(url)
        if hostname in self.BLOCKED_HOSTNAMES:
            return False, f"Blocked: cloud metadata hostname {hostname}"

        # Check if it's an IP address
        ip = self._extract_ip(hostname)
        if ip:
            for prefix in self.BLOCKED_IP_PREFIXES:
                if ip.startswith(prefix):
                    return False, f"Blocked: reserved IP range"

            for start, end in self.BLOCKED_RANGES:
                if self._ip_in_range(ip, start, end):
                    return False, f"Blocked: private network {start}/{end}"

        return True, ""

    def _extract_hostname(self, url: str) -> str:
        """Extract hostname from URL."""
        # Remove protocol
        hostname = re.sub(r"https?://", "", url)
        # Remove path
        hostname = hostname.split("/")[0]
        # Remove port
        hostname = hostname.split(":")[0]
        return hostname.lower()

    def _extract_ip(self, hostname: str) -> Optional[str]:
        """Extract IP from hostname if it's an IP."""
        # IPv4
        parts = hostname.split(".")
        if len(parts) == 4 and all(p.isdigit() for p in parts):
            return hostname
        # IPv6 (simplified)
        if ":" in hostname:
            return hostname
        return None

    def _ip_in_range(self, ip: str, start: str, end: str) -> bool:
        """Check if IP is in range (simplified)."""
        try:
            ip_num = self._ip_to_int(ip)
            start_num = self._ip_to_int(start)
            end_num = self._ip_to_int(end)
            return start_num <= ip_num <= end_num
        except (ValueError, TypeError):
            return False

    def _ip_to_int(self, ip: str) -> int:
        """Convert IPv4 to integer."""
        parts = ip.split(".")
        if len(parts) != 4:
            raise ValueError("Not IPv4")
        return (int(parts[0]) << 24) + (int(parts[1]) << 16) + (int(parts[2]) << 8) + int(parts[3])


class PromptInjectionDetector:
    """Detect prompt injection in context files."""

    SUSPICIOUS_PATTERNS = [
        (r"ignore\s+(all\s+)?previous\s+instructions", "instruction override"),
        (r"disregard\s+(all\s+)?previous", "instruction override"),
        (r"forget\s+everything", "instruction override"),
        (r"you\s+are\s+now", "role hijack"),
        (r"act\s+as\s+if", "role hijack"),
        (r"<script>", "HTML injection"),
        (r"<!--.*?-->", "hidden HTML comment"),
        (r"\.env", "credential access"),
        (r"credentials", "credential access"),
        (r"\.netrc", "credential access"),
        (r"curl\s+.*-d", "data exfiltration"),
        (r"wget\s+.*--post", "data exfiltration"),
        (r"\\u200[b-e]", "invisible unicode"),
        (r"\\u202[a-b]", "bidirectional override"),
        (r"\\ufeff", "zero-width no-break space"),
    ]

    def scan_file(self, content: str) -> tuple[bool, list[str]]:
        """Scan file content for prompt injection.

        Returns:
            Tuple of (has_injection, list of findings)
        """
        findings = []

        for pattern, description in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                findings.append(description)

        return len(findings) > 0, findings

    def scan_file_safe(self, filepath: str) -> tuple[bool, list[str]]:
        """Scan a file for prompt injection."""
        try:
            content = Path(filepath).read_text(encoding="utf-8", errors="ignore")
            return self.scan_file(content)
        except Exception as e:
            logger.error(f"Failed to scan file {filepath}: {e}")
            return False, []


class SecurityManager:
    """Central security manager."""

    def __init__(self, config: dict = None) -> None:
        config = config or {}
        self.ssrf = SSRFProtector(
            allow_private=config.get("allow_private_urls", False)
        )
        self.injection = PromptInjectionDetector()

    def check_url(self, url: str) -> tuple[bool, str]:
        """Check URL safety."""
        return self.ssrf.check_url(url)

    def scan_context_file(self, filepath: str) -> tuple[bool, list[str]]:
        """Scan context file for injection."""
        return self.injection.scan_file_safe(filepath)
