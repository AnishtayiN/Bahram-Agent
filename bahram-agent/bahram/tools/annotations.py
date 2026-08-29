"""Tool result annotations for Bahram Agent."""

from __future__ import annotations

import logging
import signal
from typing import Any

logger = logging.getLogger(__name__)


class ToolResultAnnotator:
    """Annotate tool results with helpful information."""

    @staticmethod
    def annotate_exit_code(exit_code: int) -> str:
        """Annotate exit code with human-readable explanation."""
        if exit_code == 0:
            return ""

        # Negative codes = signal (subprocess convention)
        if exit_code < 0:
            sig = -exit_code
            signal_names = {
                9: "SIGKILL — often OOM killer or explicit kill -9",
                15: "SIGTERM — graceful termination",
                6: "SIGABRT — abort called",
                11: "SIGSEGV — segmentation fault",
                13: "SIGPIPE — broken pipe",
                24: "SIGXCPU — CPU time limit exceeded",
                25: "SIGXFSZ — file size limit exceeded",
            }
            name = signal_names.get(sig, f"signal {sig}")
            return f"Terminated by signal {sig}: {name}"

        # Positive codes
        code_explanations = {
            1: "General error",
            2: "Misuse of shell command",
            126: "Command found but not executable",
            127: "Command not found",
            128: "Invalid exit argument",
            130: "Script terminated by Ctrl+C (SIGINT)",
            137: "Killed (SIGKILL) — often OOM killer",
            139: "Segmentation fault (SIGSEGV)",
            141: "Broken pipe (SIGPIPE)",
        }
        return code_explanations.get(exit_code, f"Exit code {exit_code}")

    @staticmethod
    def detect_utf16(content: bytes) -> tuple[bool, str]:
        """Detect UTF-16 encoding and transcode."""
        # Check for BOM
        if content[:2] in [b'\xff\xfe', b'\xfe\xff']:
            try:
                decoded = content.decode('utf-16')
                return True, decoded
            except Exception:
                pass

        # Check byte patterns
        if len(content) > 2 and content[0] == 0 and content[1] != 0:
            # Potential UTF-16LE
            if len(content) % 2 == 0:
                try:
                    decoded = content.decode('utf-16-le')
                    if '\x00' not in decoded:
                        return True, decoded
                except Exception:
                    pass

        return False, ""

    @staticmethod
    def annotate_result(result: dict) -> dict:
        """Add annotations to a tool result."""
        if "exit_code" in result:
            annotation = ToolResultAnnotator.annotate_exit_code(result["exit_code"])
            if annotation:
                result["_annotation"] = annotation

        if "stdout" in result:
            content = result["stdout"]
            if isinstance(content, bytes):
                is_utf16, decoded = ToolResultAnnotator.detect_utf16(content)
                if is_utf16:
                    result["stdout"] = decoded
                    result["_utf16_converted"] = True

        return result
