"""
Protection.

Public objects: ``SSRFProtector``, ``PromptInjectionDetector``, ``SecurityManager``.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SSRFProtector:
    """Block outbound requests that would reach internal or reserved networks.

    The guard answers one question - "may this URL be fetched?" - and it is
    deliberately pessimistic: anything that is not a globally routable
    unicast address is refused.

    Two things the previous implementation got wrong, both of which made the
    guard trivially bypassable:

    * only a literal dotted-quad in the URL was ever checked.  ``localhost``,
      any internal hostname, and the numeric spellings of a loopback address
      (``http://2130706433/``, ``http://0x7f000001/``) all sailed through.
    * IPv6 was matched by string prefix, so ``[::ffff:127.0.0.1]`` - the
      IPv4-mapped loopback - did not match the ``::1`` prefix and was allowed.

    Host names are now resolved and *every* returned address is checked.
    """

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

    #: names that always mean "this machine", whatever DNS says
    LOOPBACK_HOSTNAMES = frozenset(
        {
            "localhost",
            "localhost.localdomain",
            "ip6-localhost",
            "ip6-loopback",
        }
    )

    def __init__(self, allow_private: bool = False) -> None:
        self.allow_private = allow_private

    def check_url(self, url: str) -> tuple[bool, str]:
        """Decide whether ``url`` may be fetched.

        Args:
            url (str): the absolute URL the caller wants to request.

        Returns:
            tuple[bool, str]: ``(allowed, reason)``.  ``reason`` is empty when
                the URL is allowed and is the human readable cause otherwise.
        """
        if self.allow_private:
            return (True, "")

        hostname = self._extract_hostname(url)
        if not hostname:
            return (False, "Blocked: URL has no host")

        if hostname in self.BLOCKED_HOSTNAMES:
            return (False, f"Blocked: cloud metadata hostname {hostname}")

        if hostname in self.LOOPBACK_HOSTNAMES or hostname.endswith(".localhost"):
            return (False, f"Blocked: loopback hostname {hostname}")

        literal = self._parse_ip(hostname)
        if literal is not None:
            return self._verdict_for_ip(literal, hostname)

        return self._verdict_for_hostname(hostname)

    def _verdict_for_hostname(self, hostname: str) -> tuple[bool, str]:
        """Resolve ``hostname`` and refuse it if any address is not global.

        A name that refuses to resolve is allowed through: the fetch itself
        will fail, so there is nothing to protect, and refusing would make
        every offline deployment unusable.  Note the residual risk - a name
        that resolves to a public address here and to a private one when the
        request is actually made (DNS rebinding) is not caught.  Closing that
        requires pinning the resolved address on the socket.
        """
        try:
            infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        except (OSError, UnicodeError) as exc:
            logger.debug("SSRF: could not resolve %s (%s); allowing", hostname, exc)
            return (True, "")

        addresses = {info[4][0] for info in infos}
        if not addresses:
            return (True, "")

        for address in sorted(addresses):
            parsed = ipaddress.ip_address(address)
            allowed, reason = self._verdict_for_ip(parsed, hostname)
            if not allowed:
                return (allowed, reason)
        return (True, "")

    def _verdict_for_ip(self, ip: Any, hostname: str) -> tuple[bool, str]:
        """Classify a single address, refusing everything non-global."""
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
            return self._verdict_for_ip(ip.ipv4_mapped, hostname)

        if ip.is_multicast:
            return (False, f"Blocked: multicast address {ip}")
        if ip.is_unspecified:
            return (False, f"Blocked: unspecified address {ip}")
        if ip.is_loopback:
            return (False, f"Blocked: loopback address {ip}")
        if ip.is_link_local:
            return (False, f"Blocked: link-local address {ip}")
        if ip.is_reserved:
            return (False, f"Blocked: reserved address {ip}")
        if not ip.is_global:
            return (False, f"Blocked: non-routable address {ip} ({hostname})")
        return (True, "")

    def _extract_hostname(self, url: str) -> str:
        """Return the lower-cased host from ``url``, without port or userinfo."""
        host = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", url)
        host = host.split("?")[0].split("#")[0]
        host = host.split("/")[0]
        if "@" in host:  # http://user:pass@host/ - the host is what matters
            host = host.rsplit("@", 1)[1]
        if host.startswith("["):  # bracketed IPv6 literal, port included
            host = host[: host.find("]") + 1] if "]" in host else host
        elif host.count(":") == 1:
            host = host.split(":")[0]
        return host.lower().strip()

    def _parse_ip(self, hostname: str) -> Any | None:
        """Return the address object for ``hostname``, or ``None`` if it is a name.

        Handles bracketed IPv6 literals and the integer, hex and octal
        spellings of an IPv4 address, which browsers and ``curl`` all accept
        and which a purely textual check therefore misses.
        """
        candidate = hostname
        if candidate.startswith("[") and candidate.endswith("]"):
            candidate = candidate[1:-1]
        try:
            return ipaddress.ip_address(candidate)
        except ValueError:
            pass
        return self._parse_ipv4_integer(candidate)

    @staticmethod
    def _parse_ipv4_integer(host: str) -> Any | None:
        """Decode ``2130706433`` / ``0x7f000001`` / ``017700000001`` to 127.0.0.1."""
        if not host or not re.fullmatch(r"0[xX][0-9a-fA-F]+|0[0-7]*|[1-9][0-9]*", host):
            return None
        try:
            value = int(host, 0) if host.startswith("0") and len(host) > 1 else int(host)
        except ValueError:
            return None
        if not 0 <= value <= 0xFFFFFFFF:
            return None
        return ipaddress.ip_address(value)


class PromptInjectionDetector:
    """
    Prompt injection detector.
    """

    SUSPICIOUS_PATTERNS = [
        (r"ignore\s+(all\s+)?previous\s+instructions", "instruction override"),
        (r"disregard\s+(all\s+|the\s+|your\s+)?previous", "instruction override"),
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
        (r"[\u200b-\u200e]", "invisible unicode"),
        (r"[\u202a-\u202e]", "bidirectional override"),
        (r"\ufeff", "zero-width no-break space"),
    ]

    def scan_file(self, content: str) -> tuple[bool, list[str]]:
        """
        Scan file.

        Args:
            content (str): text content to process.

        Returns:
            tuple[bool, list[str]]: a sequence of bool, list[str] entries (empty when there is
                nothing to report).
        """
        findings = []

        for pattern, description in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                findings.append(description)

        return len(findings) > 0, findings

    def scan_file_safe(self, filepath: str) -> tuple[bool, list[str]]:
        """
        Scan file safe.

        Args:
            filepath (str): filepath string.

        Returns:
            tuple[bool, list[str]]: a sequence of bool, list[str] entries (empty when there is
                nothing to report).
        """
        try:
            content = Path(filepath).read_text(encoding="utf-8", errors="ignore")
            return self.scan_file(content)
        except Exception as e:
            logger.error(f"Failed to scan file {filepath}: {e}")
            return False, []


class SecurityManager:
    """
    Security manager.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """
        Initialise a SecurityManager instance.

        Args:
            config (dict): configuration object. Defaults to ``None``.
        """
        config = config or {}
        self.ssrf = SSRFProtector(allow_private=config.get("allow_private_urls", False))
        self.injection = PromptInjectionDetector()

    def check_url(self, url: str) -> tuple[bool, str]:
        """
        Check url.

        Args:
            url (str): url string.

        Returns:
            tuple[bool, str]: a sequence of bool, str entries (empty when there is nothing to
                report).
        """
        return self.ssrf.check_url(url)

    def scan_context_file(self, filepath: str) -> tuple[bool, list[str]]:
        """
        Scan context file.

        Args:
            filepath (str): filepath string.

        Returns:
            tuple[bool, list[str]]: a sequence of bool, list[str] entries (empty when there is
                nothing to report).
        """
        return self.injection.scan_file_safe(filepath)
