from __future__ import annotations

import fnmatch
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

class ApprovalMode(str, Enum):
    ""

    SMART = "smart"
    MANUAL = "manual"
    OFF = "off"

@dataclass
class ApprovalConfig:
    ""

    mode: ApprovalMode = ApprovalMode.SMART
    timeout: int = 300
    cron_mode: str = "deny"
    single_query_mode: str = "deny"
    deny: list[str] = field(default_factory=list)
    allowlist: list[str] = field(default_factory=list)

HARDLINE_BLOCKLIST = [
    "rm -rf /",
    "rm -rf --no-preserve-root /",
    ":(){ :|:& };:",
    "mkfs.* /dev/*",
    "dd if=/dev/zero of=/dev/*",
    "dd if=/dev/zero of=/dev/sd*",
]

DANGEROUS_PATTERNS = [

    (r"rm\s+(-[a-zA-Z]*r[a-zA-Z]*|-[a-zA-Z]*\s+-[a-zA-Z]*r|-[a-zA-Z]*\s+--recursive)\s+", "Recursive delete"),
    (r"rm\s+.*\s+/", "Delete in root path"),

    (r"chmod\s+(777|666|o\+w|a\+w)", "Unsafe permissions"),
    (r"chmod\s+--recursive\s+", "Recursive chmod"),
    (r"chown\s+(-R|--recursive)\s+root", "Recursive chown to root"),

    (r"mkfs", "Format filesystem"),
    (r"dd\s+if=", "Disk copy"),
    (r">\s*/dev/sd", "Write to block device"),

    (r"DROP\s+(TABLE|DATABASE)", "SQL DROP"),
    (r"DELETE\s+FROM\s+.*\s+(?!WHERE)", "SQL DELETE without WHERE"),
    (r"TRUNCATE\s+TABLE", "SQL TRUNCATE"),

    (r">\s*/etc/", "Overwrite system config"),
    (r"systemctl\s+(stop|restart|disable|mask)", "System service control"),
    (r"kill\s+-9\s+-1", "Kill all processes"),
    (r"pkill\s+-9", "Force kill processes"),

    (r":\(\)\s*\{", "Fork bomb pattern"),

    (r"bash\s+-[cC]", "Shell command execution"),
    (r"sh\s+-[cC]", "Shell command execution"),
    (r"zsh\s+-c", "Shell command execution"),
    (r"python\s+-e", "Script execution"),
    (r"perl\s+-e", "Script execution"),
    (r"ruby\s+-e", "Script execution"),

    (r"curl\s+.*\|\s*sh", "Pipe remote content to shell"),
    (r"wget\s+.*\|\s*sh", "Pipe remote content to shell"),
    (r"bash\s*<\(curl", "Execute remote script"),
    (r"sh\s*<\(wget", "Execute remote script"),

    (r"tee\s+.*(/etc/|~/.ssh/|~/.hermes/\.env)", "Overwrite sensitive file"),
    (r">\s*~/.ssh/", "Overwrite SSH file"),
    (r">\s*~/.hermes/\.env", "Overwrite env file"),

    (r"find\s+.*-exec\s+rm", "Find with rm"),
    (r"find\s+.*-delete", "Find delete"),

    (r"docker\s+(stop|kill|restart)", "Container lifecycle"),
    (r"docker\s+compose\s+(down|stop|kill|restart)", "Container lifecycle"),
    (r"(DOCKER_HOST|DOCKER_CONTEXT)=", "Docker daemon redirect"),
]

class ApprovalSystem:
    ""

    def __init__(self, config: ApprovalConfig = None) -> None:
        self.config = config or ApprovalConfig()
        self._session_allowlist: list[str] = []

    def check_command(self, command: str) -> tuple[bool, str]:
        ""

        for pattern in HARDLINE_BLOCKLIST:
            if re.search(pattern, command, re.IGNORECASE):
                return True, f"HARDLINE BLOCKED: {pattern}"

        for deny_pattern in self.config.deny:
            if fnmatch.fnmatch(command.lower(), deny_pattern.lower()):
                return True, f"DENIED by policy: {deny_pattern}"

        if self._is_in_allowlist(command):
            return False, ""

        for pattern, description in DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True, description

        return False, ""

    def _is_in_allowlist(self, command: str) -> bool:
        ""
        for pattern in self.config.allowlist + self._session_allowlist:
            if fnmatch.fnmatch(command.lower(), pattern.lower()):
                return True
        return False

    def approve_once(self, command: str) -> None:
        ""
        self._session_allowlist.append(command)

    def approve_always(self, command: str) -> None:
        ""
        self.config.allowlist.append(command)

    def get_approval_mode(self) -> ApprovalMode:
        ""
        return self.config.mode

    def should_prompt(self, command: str) -> bool:
        ""
        if self.config.mode == ApprovalMode.OFF:
            return False

        is_dangerous, _ = self.check_command(command)
        if not is_dangerous:
            return False

        if self._is_in_allowlist(command):
            return False

        return True

    def assess_risk(self, command: str) -> str:
        ""
        is_dangerous, reason = self.check_command(command)

        if not is_dangerous:
            return "low"

        if "HARDLINE" in reason:
            return "critical"

        if any(x in reason.lower() for x in ["delete", "drop", "truncate", "kill"]):
            return "high"

        if any(x in reason.lower() for x in ["chmod", "chown", "systemctl"]):
            return "medium"

        return "medium"
