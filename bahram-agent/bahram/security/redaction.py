"""Scrub credentials out of text before it is logged or shown to a model.

Public objects: ``REDACTION_PATTERNS``, ``redact``, ``register_secret_value``,
``SecretRedactingFilter``.

Tool output, provider errors and tracebacks routinely contain API keys.  Left
alone they end up in log files, in crash reports and in the next prompt sent
to the model, which is how a leaked key spreads.  This module removes
credential-shaped substrings from any text it is given.

It is wired in two places, so it is not dead code:

* :meth:`SecretRedactingFilter.install` is called from ``Agent.__init__`` and
  attaches to the root logger, so every log record emitted by Bahram (and by
  the HTTP/SDK libraries it drives) is scrubbed before the handler sees it.
* :meth:`bahram.core.secrets.SecretsManager.redact` uses :func:`redact` plus
  the exact values it holds, so a known secret is removed even when it does
  not look like one.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

logger = logging.getLogger(__name__)

#: ``(compiled pattern, replacement)`` pairs applied in order by :func:`redact`.
#: The patterns are deliberately broad - a false positive costs a developer one
#: log line, a false negative leaks a credential.
REDACTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Provider/vendor key formats
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "sk-***REDACTED***"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{16,}"), "sk-ant-***REDACTED***"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "ghp_***REDACTED***"),
    (re.compile(r"gho_[A-Za-z0-9]{20,}"), "gho_***REDACTED***"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "github_pat_***REDACTED***"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA***REDACTED***"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{30,}"), "AIza***REDACTED***"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"), "xox?-***REDACTED***"),
    # JWT: header.payload.signature
    (
        re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),
        "***REDACTED-JWT***",
    ),
    # Authorization headers and bearer tokens
    (
        re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._\-+/=]{8,}"),
        r"\1 ***REDACTED***",
    ),
    (
        re.compile(
            r"(?i)\b(authorization|proxy-authorization)\s*[:=]\s*\S+",
        ),
        r"\1: ***REDACTED***",
    ),
    # key=value assignments, in source, URLs and shell commands
    (
        re.compile(
            r"(?i)\b(api[_-]?key|apikey|access[_-]?token|auth[_-]?token|secret[_-]?key|"
            r"client[_-]?secret|private[_-]?key|passphrase|passwd|password|token)"
            r"(\s*[:=]\s*|['\"]?\s*[:=]\s*['\"]?)([^\s&'\"<>]{4,})"
        ),
        r"\1\2***REDACTED***",
    ),
    # PEM private key blocks
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
        "-----BEGIN ***REDACTED*** PRIVATE KEY-----",
    ),
    # Credentials embedded in a URL: https://user:pass@host
    (
        re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://)([^/\s:@]+):([^/\s@]+)@"),
        r"\1***REDACTED***:***REDACTED***@",
    ),
]

#: Exact values registered by :func:`register_secret_value`.
_EXTRA_VALUES: set[str] = set()

#: Short values are too likely to appear in ordinary text to be worth matching.
_MIN_EXTRA_VALUE_LENGTH = 8


def register_secret_value(value: str) -> None:
    """Remember a concrete secret so :func:`redact` removes it verbatim.

    Args:
        value (str): the secret itself.  Values shorter than eight characters
            are ignored: they collide with ordinary words far too often.
    """
    if value and len(value) >= _MIN_EXTRA_VALUE_LENGTH:
        _EXTRA_VALUES.add(value)


def clear_registered_values() -> None:
    """Forget every value registered with :func:`register_secret_value`.

    Intended for tests and for shutdown paths that must not hold secrets.
    """
    _EXTRA_VALUES.clear()


def redact(text: str, extra_values: Iterable[str] = ()) -> str:
    """Return ``text`` with credential-looking substrings replaced.

    Args:
        text (str): arbitrary text - a log line, tool output, an error.
        extra_values (Iterable[str]): concrete values to remove verbatim, on
            top of the values already registered globally.

    Returns:
        str: the scrubbed text.  Non-string input is returned unchanged so the
            helper can sit in a logging filter without a type guard.
    """
    if not isinstance(text, str) or not text:
        return text

    scrubbed = text
    for pattern, replacement in REDACTION_PATTERNS:
        scrubbed = pattern.sub(replacement, scrubbed)

    for value in sorted(
        {v for v in _EXTRA_VALUES if len(v) >= _MIN_EXTRA_VALUE_LENGTH}
        | {v for v in extra_values if v and len(v) >= _MIN_EXTRA_VALUE_LENGTH},
        key=len,
        reverse=True,
    ):
        scrubbed = scrubbed.replace(value, "***REDACTED***")

    return scrubbed


class SecretRedactingFilter(logging.Filter):
    """Logging filter that scrubs ``record.msg`` and its arguments.

    Installed once on the root logger by :meth:`install`, it applies to every
    record that flows through Python's logging system, including records
    produced by ``httpx``, ``openai`` and the other libraries Bahram drives.
    """

    _installed = False

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact the message and arguments of ``record`` in place.

        Args:
            record (logging.LogRecord): the record about to be emitted.

        Returns:
            bool: always ``True`` - the record is rewritten, never dropped.
        """
        try:
            if isinstance(record.msg, str):
                record.msg = redact(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {k: redact(str(v)) for k, v in record.args.items()}
                elif isinstance(record.args, tuple):
                    record.args = tuple(
                        redact(str(arg)) if isinstance(arg, str) else arg for arg in record.args
                    )
            if record.exc_text:
                record.exc_text = redact(record.exc_text)
        except Exception as exc:  # a logging filter must never raise
            logger.debug("Redaction filter failed: %s", exc)
        return True

    @classmethod
    def install(cls, target: logging.Logger | None = None) -> bool:
        """Attach the filter to a logger, once.

        Args:
            target (logging.Logger | None): logger to protect. Defaults to the
                root logger so third-party libraries are covered too.

        Returns:
            bool: ``True`` if this call attached the filter, ``False`` if an
                instance was already present (or globally installed).
        """
        log = target if target is not None else logging.getLogger()
        for existing in log.filters:
            if isinstance(existing, cls):
                return False
        if cls._installed and log is logging.getLogger():
            return False
        log.addFilter(cls())
        if log is logging.getLogger():
            cls._installed = True
        return True

    @classmethod
    def uninstall(cls, target: logging.Logger | None = None) -> int:
        """Detach every instance of this filter from a logger.

        Args:
            target (logging.Logger | None): logger to clean. Defaults to the
                root logger.

        Returns:
            int: how many filters were removed.
        """
        log = target if target is not None else logging.getLogger()
        keep = [f for f in log.filters if not isinstance(f, cls)]
        removed = len(log.filters) - len(keep)
        log.filters[:] = keep
        if log is logging.getLogger():
            cls._installed = False
        return removed
