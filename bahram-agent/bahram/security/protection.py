from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class SSRFProtector:

    BLOCKED_RANGES = [
        ("10.0.0.0", "10.255.255.255"),
        ("172.16.0.0", "172.31.255.255"),
        ("192.168.0.0", "192.168.255.255"),
        ("127.0.0.0", "127.255.255.255"),
        ("169.254.0.0", "169.254.255.255"),
        ("100.64.0.0", "100.127.255.255"),
    ]

    BLOCKED_HOSTNAMES = [
        "metadata.google.internal",
        "metadata.goog",
        "169.254.169.254",
    ]

    BLOCKED_IP_PREFIXES = [
        "fe80:",
        "fc00:",
        "fd00:",
        "::1",
    ]

    def __init__(self, allow_private: bool = False) -> None:
        self.allow_private = allow_private

    def check_url(self, url: str) -> tuple[bool, str]:
        if self.allow_private:
            return True, ""

        hostname = self._extract_hostname(url)
        if hostname in self.BLOCKED_HOSTNAMES:
            return False, f"Blocked: cloud metadata hostname {hostname}"

        ip = self._extract_ip(hostname)
        if ip:
            for prefix in self.BLOCKED_IP_PREFIXES:
                if ip.startswith(prefix):
                    return False, "Blocked: reserved IP range"

            for start, end in self.BLOCKED_RANGES:
                if self._ip_in_range(ip, start, end):
                    return False, f"Blocked: private network {start}/{end}"

        return True, ""

    def _extract_hostname(self, url: str) -> str:

        hostname = re.sub(r"https?://", "", url)

        hostname = hostname.split("/")[0]

        hostname = hostname.split(":")[0]
        return hostname.lower()

    def _extract_ip(self, hostname: str) -> str | None:

        parts = hostname.split(".")
        if len(parts) == 4 and all(p.isdigit() for p in parts):
            return hostname

        if ":" in hostname:
            return hostname
        return None

    def _ip_in_range(self, ip: str, start: str, end: str) -> bool:
        try:
            ip_num = self._ip_to_int(ip)
            start_num = self._ip_to_int(start)
            end_num = self._ip_to_int(end)
            return start_num <= ip_num <= end_num
        except (ValueError, TypeError):
            return False

    def _ip_to_int(self, ip: str) -> int:
        parts = ip.split(".")
        if len(parts) != 4:
            raise ValueError("Not IPv4")
        return (int(parts[0]) << 24) + (int(parts[1]) << 16) + (int(parts[2]) << 8) + int(parts[3])

class PromptInjectionDetector:

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
        findings = []

        for pattern, description in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                findings.append(description)

        return len(findings) > 0, findings

    def scan_file_safe(self, filepath: str) -> tuple[bool, list[str]]:
        try:
            content = Path(filepath).read_text(encoding="utf-8", errors="ignore")
            return self.scan_file(content)
        except Exception as e:
            logger.error(f"Failed to scan file {filepath}: {e}")
            return False, []

class SecurityManager:

    def __init__(self, config: dict = None) -> None:
        config = config or {}
        self.ssrf = SSRFProtector(
            allow_private=config.get("allow_private_urls", False)
        )
        self.injection = PromptInjectionDetector()

    def check_url(self, url: str) -> tuple[bool, str]:
        return self.ssrf.check_url(url)

    def scan_context_file(self, filepath: str) -> tuple[bool, list[str]]:
        return self.injection.scan_file_safe(filepath)
