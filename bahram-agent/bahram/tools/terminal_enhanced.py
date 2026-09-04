"""
Terminal enhanced.

Public objects: ``PTYSession``, ``PTYManager``, ``SudoManager``, ``ShellInitHandler``.
"""

from __future__ import annotations

import fcntl
import logging
import os
import pty
import select
import struct
import termios
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PTYSession:
    """
    PTY session.

    Attributes:
        session_id (str): session identifier.
        pid (int): numeric value for pid.
        fd (int): numeric value for fd.
        cwd (str): cwd string.
        created_at (str): created at string.
        interactive (bool): when ``True``, enable interactive.
    """

    session_id: str
    pid: int
    fd: int
    cwd: str = ""
    created_at: str = ""
    interactive: bool = True


class PTYManager:
    """
    PTY manager.
    """

    def __init__(self) -> None:
        """
        Initialise a PTYManager instance.
        """
        self._sessions: dict[str, PTYSession] = {}

    def create_session(
        self,
        command: str = "/bin/bash",
        cwd: str = ".",
        cols: int = 80,
        rows: int = 24,
    ) -> PTYSession:
        """
        Create session.

        Args:
            command (str): shell command to execute. Defaults to ``'/bin/bash'``.
            cwd (str): cwd string. Defaults to ``'.'``.
            cols (int): numeric value for cols. Defaults to ``80``.
            rows (int): numeric value for rows. Defaults to ``24``.

        Returns:
            PTYSession: the resulting PTYSession.
        """
        import uuid
        from datetime import datetime

        session_id = str(uuid.uuid4())[:8]

        child_pid, fd = pty.openpty()

        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

        if child_pid == 0:
            os.chdir(cwd)
            os.execvp(command, [command])
        else:
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
        """
        Read output.

        Args:
            session_id (str): session identifier.
            timeout (float): timeout in seconds. Defaults to ``0.1``.

        Returns:
            str: the rendered string.

        Note:
            Coroutine - must be awaited.
        """
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
        """
        Write input.

        Args:
            session_id (str): session identifier.
            data (str): data string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
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
        """
        Resize.

        Args:
            session_id (str): session identifier.
            cols (int): numeric value for cols.
            rows (int): numeric value for rows.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
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
        """
        Close session.

        Args:
            session_id (str): session identifier.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        session = self._sessions.pop(session_id, None)
        if session:
            try:
                os.close(session.fd)
                os.kill(session.pid, 15)
            except Exception:
                logger.warning("Failed to clean up PTY session %s", session_id, exc_info=True)
            return True
        return False

    def list_sessions(self) -> list[dict]:
        """
        List sessions.

        Returns:
            list[dict]: a sequence of dict entries (empty when there is nothing to report).
        """
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
    """
    Sudo manager.
    """

    def __init__(self) -> None:
        """
        Initialise a SudoManager instance.
        """
        self._cached_password: str | None = None
        self._cache_ttl: int = 300
        self._last_auth: float = 0

    def set_password(self, password: str) -> None:
        """
        Set the password.

        Args:
            password (str): password string.
        """
        import time

        self._cached_password = password
        self._last_auth = time.time()

    def get_password(self) -> str | None:
        """
        Return the password.

        Returns:
            str | None: the resulting object, or ``None`` when it is not available.
        """
        import time

        if self._cached_password and (time.time() - self._last_auth < self._cache_ttl):
            return self._cached_password
        return None

    def clear(self) -> None:
        """
        Clear.
        """
        self._cached_password = None

    def is_cached(self) -> bool:
        """
        Return ``True`` when cached.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.
        """
        import time

        return self._cached_password is not None and (
            time.time() - self._last_auth < self._cache_ttl
        )


class ShellInitHandler:
    """
    Shell init handler.
    """

    @staticmethod
    def get_non_interactive_guard() -> str:
        """
        Return the non interactive guard.

        Returns:
            str: the rendered string.
        """
        return ""

    @staticmethod
    def get_safe_bashrc_content() -> str:
        """
        Return the safe bashrc content.

        Returns:
            str: the rendered string.
        """
        return ""

    @staticmethod
    def get_env_passthrough_vars() -> list[str]:
        """
        Return the env passthrough vars.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).
        """
        return [
            "PATH",
            "HOME",
            "USER",
            "LANG",
            "LC_ALL",
            "TERM",
            "SHELL",
            "TMPDIR",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "XDG_CACHE_HOME",
        ]
