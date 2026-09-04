"""
Terminal.

Public objects: ``TerminalConfig``, ``PTYManager``, ``SudoManager``, ``ShellInitHandler``,
    ``TerminalTool``.
"""

from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import pty
import select
import signal
import struct
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TerminalConfig:
    """
    Terminal config.

    Attributes:
        shell (str): shell string.
        cwd (str): cwd string.
        env (dict[str, str]): mapping of env.
        use_pty (bool): when ``True``, enable use pty.
        sudo (bool): when ``True``, enable sudo.
        timeout (float): timeout in seconds.
    """

    shell: str = "/bin/bash"
    cwd: str = ""
    env: dict[str, str] = field(default_factory=dict)
    use_pty: bool = True
    sudo: bool = False
    timeout: float = 60.0


class PTYManager:
    """
    PTY manager.
    """

    def __init__(self) -> None:
        """
        Initialise a PTYManager instance.
        """
        self._sessions: dict[str, int] = {}

    def create_session(self, config: TerminalConfig) -> tuple[int, int]:
        """
        Create session.

        Args:
            config (TerminalConfig): configuration object.

        Returns:
            tuple[int, int]: a sequence of int, int entries (empty when there is nothing to report).
        """
        master_fd, slave_fd = pty.openpty()

        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        winsize = struct.pack("HHHH", 24, 80, 0, 0)
        fcntl.ioctl(slave_fd, struct.unpack("H", b"TIOCSWINSZ")[0], winsize)

        return master_fd, slave_fd

    def write_session(self, master_fd: int, data: str) -> None:
        """
        Write session.

        Args:
            master_fd (int): numeric value for master fd.
            data (str): data string.
        """
        os.write(master_fd, data.encode())

    def read_session(self, master_fd: int, timeout: float = 0.1) -> str:
        """
        Read session.

        Args:
            master_fd (int): numeric value for master fd.
            timeout (float): timeout in seconds. Defaults to ``0.1``.

        Returns:
            str: the rendered string.
        """
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
        """
        Close session.

        Args:
            master_fd (int): numeric value for master fd.
        """
        try:
            os.close(master_fd)
        except OSError:
            pass


class SudoManager:
    """
    Sudo manager.
    """

    def __init__(self) -> None:
        """
        Initialise a SudoManager instance.
        """
        self._password_cache: dict[str, str] = {}
        self._cache_timeout: float = 300.0
        self._cache_timestamps: dict[str, float] = {}

    def cache_password(self, hostname: str, password: str) -> None:
        """
        Cache password.

        Args:
            hostname (str): hostname string.
            password (str): password string.
        """
        import time

        self._password_cache[hostname] = password
        self._cache_timestamps[hostname] = time.time()

    def get_password(self, hostname: str) -> str | None:
        """
        Return the password.

        Args:
            hostname (str): hostname string.

        Returns:
            str | None: the resulting object, or ``None`` when it is not available.
        """
        import time

        if hostname not in self._password_cache:
            return None

        timestamp = self._cache_timestamps.get(hostname, 0)
        if time.time() - timestamp > self._cache_timeout:
            del self._password_cache[hostname]
            del self._cache_timestamps[hostname]
            return None

        return self._password_cache[hostname]

    def clear_password(self, hostname: str) -> None:
        """
        Clear password.

        Args:
            hostname (str): hostname string.
        """
        self._password_cache.pop(hostname, None)
        self._cache_timestamps.pop(hostname, None)


class ShellInitHandler:
    """
    Shell init handler.
    """

    def __init__(self) -> None:
        """
        Initialise a ShellInitHandler instance.
        """
        self._init_commands: list[str] = []
        self._guard_patterns: list[str] = [
            "if [ -t 0 ]",
            "if [[ $- == *i* ]]",
            "if [[ $- =~ i ]]",
            "if tty -s",
            "if [ -t 1 ]",
        ]

    def get_init_script(self, shell: str = "/bin/bash") -> str:
        """
        Return the init script.

        Args:
            shell (str): shell string. Defaults to ``'/bin/bash'``.

        Returns:
            str: the rendered string.
        """
        if "zsh" in shell:
            return self._get_zsh_init()
        elif "fish" in shell:
            return self._get_fish_init()
        else:
            return self._get_bash_init()

    def _get_bash_init(self) -> str:
        return ""

    def _get_zsh_init(self) -> str:
        return ""

    def _get_fish_init(self) -> str:
        return ""

    def wrap_command(self, command: str, shell: str = "/bin/bash") -> str:
        """
        Wrap command.

        Args:
            command (str): shell command to execute.
            shell (str): shell string. Defaults to ``'/bin/bash'``.

        Returns:
            str: the rendered string.
        """
        init = self.get_init_script(shell)
        return f"{init}\n{command}"


class TerminalTool:
    """
    Terminal tool.
    """

    def __init__(self) -> None:
        """
        Initialise a TerminalTool instance.
        """
        self.pty_manager = PTYManager()
        self.sudo_manager = SudoManager()
        self.shell_handler = ShellInitHandler()
        self._config = TerminalConfig()

    async def execute(
        self,
        command: str,
        config: TerminalConfig = None,
    ) -> dict[str, Any]:
        """
        Execute the tool and return its textual result.

        Args:
            command (str): shell command to execute.
            config (TerminalConfig): configuration object. Defaults to ``None``.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
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
        master_fd, slave_fd = self.pty_manager.create_session(config)

        try:
            if not config.sudo:
                wrapped = self.shell_handler.wrap_command(command, config.shell)
            else:
                wrapped = command

            pid = os.fork()
            if pid == 0:
                os.close(master_fd)
                os.setsid()
                fcntl.ioctl(slave_fd, struct.unpack("H", b"TIOCSCTTY")[0], 0)
                os.dup2(slave_fd, 0)
                os.dup2(slave_fd, 1)
                os.dup2(slave_fd, 2)
                os.close(slave_fd)

                os.execvp(config.shell, [config.shell, "-c", wrapped])
            else:
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
