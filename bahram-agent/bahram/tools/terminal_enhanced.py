"""Enhanced terminal with PTY, sudo, shell init for Bahram Agent."""

from __future__ import annotations

import asyncio
import logging
import os
import pty
import select
import struct
import fcntl
import termios
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class PTYSession:
    """A PTY session."""

    session_id: str
    pid: int
    fd: int
    cwd: str = ""
    created_at: str = ""
    interactive: bool = True


class PTYManager:
    """Manage PTY sessions for interactive commands."""

    def __init__(self) -> None:
        self._sessions: dict[str, PTYSession] = {}

    def create_session(
        self,
        command: str = "/bin/bash",
        cwd: str = ".",
        cols: int = 80,
        rows: int = 24,
    ) -> PTYSession:
        """Create a new PTY session."""
        import uuid
        from datetime import datetime

        session_id = str(uuid.uuid4())[:8]

        # Create PTY
        child_pid, fd = pty.openpty()

        # Set terminal size
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

        if child_pid == 0:
            # Child process
            os.chdir(cwd)
            os.execvp(command, [command])
        else:
            # Parent process
            session = PTYSession(
                session_id=session_id,
                pid=child_pid,
                fd=fd,
                cwd=cwd,
                created_at=datetime.now().isoformat(),
            )
            self._sessions[session_id] = session
            return session

    async def read_output(self, session_id: str, timeout: float = 0.1) -> str:
        """Read output from PTY."""
        session = self._sessions.get(session_id)
        if not session:
            return ""

        try:
            r, _, _ = select.select([session.fd], [], [], timeout)
            if r:
                data = os.read(session.fd, 4096)
                return data.decode("utf-8", errors="replace")
        except Exception as e:
            logger.error(f"PTY read error: {e}")
        return ""

    async def write_input(self, session_id: str, data: str) -> bool:
        """Write input to PTY."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        try:
            os.write(session.fd, data.encode())
            return True
        except Exception as e:
            logger.error(f"PTY write error: {e}")
            return False

    async def resize(self, session_id: str, cols: int, rows: int) -> bool:
        """Resize PTY."""
        session = self._sessions.get(session_id)
        if not session:
            return False

        try:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(session.fd, termios.TIOCSWINSZ, winsize)
            return True
        except Exception as e:
            logger.error(f"PTY resize error: {e}")
            return False

    def close_session(self, session_id: str) -> bool:
        """Close a PTY session."""
        session = self._sessions.pop(session_id, None)
        if session:
            try:
                os.close(session.fd)
                os.kill(session.pid, 15)  # SIGTERM
            except Exception:
                pass
            return True
        return False

    def list_sessions(self) -> list[dict]:
        """List active sessions."""
        return [
            {
                "session_id": s.session_id,
                "pid": s.pid,
                "cwd": s.cwd,
                "created_at": s.created_at,
            }
            for s in self._sessions.values()
        ]


class SudoManager:
    """Manage sudo password caching."""

    def __init__(self) -> None:
        self._cached_password: Optional[str] = None
        self._cache_ttl: int = 300  # 5 minutes
        self._last_auth: float = 0

    def set_password(self, password: str) -> None:
        """Cache sudo password."""
        import time
        self._cached_password = password
        self._last_auth = time.time()

    def get_password(self) -> Optional[str]:
        """Get cached password if valid."""
        import time
        if self._cached_password and (time.time() - self._last_auth < self._cache_ttl):
            return self._cached_password
        return None

    def clear(self) -> None:
        """Clear cached password."""
        self._cached_password = None

    def is_cached(self) -> bool:
        """Check if password is cached."""
        import time
        return self._cached_password is not None and (time.time() - self._last_auth < self._cache_ttl)


class ShellInitHandler:
    """Handle shell startup files for non-interactive commands."""

    @staticmethod
    def get_non_interactive_guard() -> str:
        """Get shell guard for non-interactive mode."""
        return """# Non-interactive guard
case $- in
  *i*) ;;
  *) return;;
esac"""

    @staticmethod
    def get_safe_bashrc_content() -> str:
        """Get safe bashrc content for agent."""
        return f"""{ShellInitHandler.get_non_interactive_guard()}

# Light PATH exports (safe for non-interactive)
export PATH="$HOME/.local/bin:$PATH"
"""

    @staticmethod
    def get_env_passthrough_vars() -> list[str]:
        """Get vars safe to pass through."""
        return [
            "PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM", "SHELL", "TMPDIR",
            "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME",
        ]
