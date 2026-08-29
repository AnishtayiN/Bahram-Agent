"""Terminal tool with PTY support, sudo, and shell init handling for Bahram Agent."""

from __future__ import annotations

import asyncio
import logging
import os
import pty
import select
import signal
import struct
import fcntl
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TerminalConfig:
    """Terminal configuration."""

    shell: str = "/bin/bash"
    cwd: str = ""
    env: dict[str, str] = field(default_factory=dict)
    use_pty: bool = True
    sudo: bool = False
    timeout: float = 60.0


class PTYManager:
    """Manage pseudo-terminal sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, int] = {}

    def create_session(self, config: TerminalConfig) -> tuple[int, int]:
        """Create a new PTY session.

        Returns:
            Tuple of (master_fd, slave_fd)
        """
        master_fd, slave_fd = pty.openpty()

        # Set non-blocking
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        # Set window size
        winsize = struct.pack("HHHH", 24, 80, 0, 0)
        fcntl.ioctl(slave_fd, struct.unpack("H", b"TIOCSWINSZ")[0], winsize)

        return master_fd, slave_fd

    def write_session(self, master_fd: int, data: str) -> None:
        """Write to a PTY session."""
        os.write(master_fd, data.encode())

    def read_session(self, master_fd: int, timeout: float = 0.1) -> str:
        """Read from a PTY session."""
        output = ""
        try:
            r, _, _ = select.select([master_fd], [], [], timeout)
            if r:
                data = os.read(master_fd, 1024)
                output = data.decode("utf-8", errors="replace")
        except (OSError, ValueError):
            pass
        return output

    def close_session(self, master_fd: int) -> None:
        """Close a PTY session."""
        try:
            os.close(master_fd)
        except OSError:
            pass


class SudoManager:
    """Manage sudo password caching."""

    def __init__(self) -> None:
        self._password_cache: dict[str, str] = {}
        self._cache_timeout: float = 300.0  # 5 minutes
        self._cache_timestamps: dict[str, float] = {}

    def cache_password(self, hostname: str, password: str) -> None:
        """Cache a sudo password."""
        import time
        self._password_cache[hostname] = password
        self._cache_timestamps[hostname] = time.time()

    def get_password(self, hostname: str) -> Optional[str]:
        """Get cached sudo password."""
        import time
        if hostname not in self._password_cache:
            return None

        # Check expiry
        timestamp = self._cache_timestamps.get(hostname, 0)
        if time.time() - timestamp > self._cache_timeout:
            del self._password_cache[hostname]
            del self._cache_timestamps[hostname]
            return None

        return self._password_cache[hostname]

    def clear_password(self, hostname: str) -> None:
        """Clear cached password."""
        self._password_cache.pop(hostname, None)
        self._cache_timestamps.pop(hostname, None)


class ShellInitHandler:
    """Handle shell initialization for non-interactive mode."""

    def __init__(self) -> None:
        self._init_commands: list[str] = []
        self._guard_patterns: list[str] = [
            "if [ -t 0 ]",
            "if [[ $- == *i* ]]",
            "if [[ $- =~ i ]]",
            "if tty -s",
            "if [ -t 1 ]",
        ]

    def get_init_script(self, shell: str = "/bin/bash") -> str:
        """Get shell initialization script."""
        if "zsh" in shell:
            return self._get_zsh_init()
        elif "fish" in shell:
            return self._get_fish_init()
        else:
            return self._get_bash_init()

    def _get_bash_init(self) -> str:
        """Get bash init for non-interactive mode."""
        return """#!/bin/bash
# Non-interactive shell init
export TERM=dumb
export NO_COLOR=1
unset HISTFILE
export HISTSIZE=0
# Skip interactive-only configs
if [ -f ~/.bashrc ]; then
    source ~/.bashrc 2>/dev/null || true
fi
"""

    def _get_zsh_init(self) -> str:
        """Get zsh init for non-interactive mode."""
        return """#!/bin/zsh
# Non-interactive shell init
export TERM=dumb
export NO_COLOR=1
unset HISTFILE
# Skip interactive-only configs
[[ -f ~/.zshrc ]] && source ~/.zshrc 2>/dev/null || true
"""

    def _get_fish_init(self) -> str:
        """Get fish init for non-interactive mode."""
        return """#!/usr/bin/env fish
# Non-interactive shell init
set -gx TERM dumb
set -gx NO_COLOR 1
"""

    def wrap_command(self, command: str, shell: str = "/bin/bash") -> str:
        """Wrap command to skip interactive init."""
        init = self.get_init_script(shell)
        return f"{init}\n{command}"


class TerminalTool:
    """Enhanced terminal tool with PTY, sudo, and shell init."""

    def __init__(self) -> None:
        self.pty_manager = PTYManager()
        self.sudo_manager = SudoManager()
        self.shell_handler = ShellInitHandler()
        self._config = TerminalConfig()

    async def execute(
        self,
        command: str,
        config: TerminalConfig = None,
    ) -> dict[str, Any]:
        """Execute a command."""
        cfg = config or self._config

        if cfg.use_pty:
            return await self._execute_pty(command, cfg)
        else:
            return await self._execute_subprocess(command, cfg)

    async def _execute_pty(
        self,
        command: str,
        config: TerminalConfig,
    ) -> dict[str, Any]:
        """Execute with PTY."""
        master_fd, slave_fd = self.pty_manager.create_session(config)

        try:
            # Wrap command if needed
            if not config.sudo:
                wrapped = self.shell_handler.wrap_command(command, config.shell)
            else:
                wrapped = command

            # Start process
            pid = os.fork()
            if pid == 0:
                # Child process
                os.close(master_fd)
                os.setsid()
                fcntl.ioctl(slave_fd, struct.unpack("H", b"TIOCSCTTY")[0], 0)
                os.dup2(slave_fd, 0)
                os.dup2(slave_fd, 1)
                os.dup2(slave_fd, 2)
                os.close(slave_fd)

                # Execute
                os.execvp(config.shell, [config.shell, "-c", wrapped])
            else:
                # Parent process
                os.close(slave_fd)
                output = ""
                start = asyncio.get_event_loop().time()

                while True:
                    if asyncio.get_event_loop().time() - start > config.timeout:
                        os.kill(pid, signal.SIGTERM)
                        break

                    data = self.pty_manager.read_session(master_fd, 0.1)
                    if data:
                        output += data
                    else:
                        # Check if process exited
                        try:
                            wpid, status = os.waitpid(pid, os.WNOHANG)
                            if wpid:
                                break
                        except ChildProcessError:
                            break

                self.pty_manager.close_session(master_fd)
                return {
                    "stdout": output,
                    "stderr": "",
                    "exit_code": 0,
                }

        except Exception as e:
            self.pty_manager.close_session(master_fd)
            return {
                "stdout": "",
                "stderr": str(e),
                "exit_code": 1,
            }

    async def _execute_subprocess(
        self,
        command: str,
        config: TerminalConfig,
    ) -> dict[str, Any]:
        """Execute without PTY."""
        wrapped = self.shell_handler.wrap_command(command, config.shell)

        proc = await asyncio.create_subprocess_shell(
            wrapped,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=config.cwd or None,
            env=config.env or None,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=config.timeout,
            )
            return {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "exit_code": proc.returncode,
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {
                "stdout": "",
                "stderr": "Command timed out",
                "exit_code": -1,
            }
