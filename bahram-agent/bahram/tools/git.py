"""
Git.

Public objects: ``GitCommit``, ``GitTool``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GitCommit:
    """
    Git commit.

    Attributes:
        hash (str): hash string.
        author (str): author string.
        date (str): date string.
        message (str): message to process.
    """

    hash: str
    author: str
    date: str
    message: str


class GitTool:
    """
    Git tool.
    """

    def __init__(self, repo_path: str = ".") -> None:
        """
        Initialise a GitTool instance.

        Args:
            repo_path (str): repo path string. Defaults to ``'.'``.
        """
        self.repo_path = repo_path

    async def _run(self, *args: str) -> dict[str, Any]:
        """Run ``git`` with ``args`` inside :attr:`repo_path`.

        Args:
            *args (str): git sub-command and its arguments, one per element.

        Returns:
            dict[str, Any]: ``stdout``, ``stderr`` and ``returncode``, with both
            streams decoded as UTF-8.

        Note:
            Coroutine - must be awaited.

        Note:
            Uses ``create_subprocess_exec`` with an argv list instead of
            ``create_subprocess_shell`` with an interpolated string.  The shell
            form broke every command containing shell metacharacters -
            ``--format=%(refname:short)`` aborted with ``Syntax error: "("
            unexpected``, and ``--format=%H|%an|%ai|%s`` had its ``%s``
            swallowed - and a commit message such as ``fix: " && rm -rf /``
            would have executed arbitrary commands.
        """
        argv = ["git", "-C", self.repo_path, *args]
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return {
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "returncode": proc.returncode,
        }

    async def status(self) -> dict[str, Any]:
        """
        Status.

        Returns:
            dict[str, Any]: a mapping of str, Any.

        Note:
            Coroutine - must be awaited.
        """
        result = await self._run("status", "--porcelain")
        files = []
        # `git status --porcelain` emits "XY <path>"; the two status columns
        # are significant, so only line terminators may be trimmed.  A plain
        # .strip() also removed the leading space of the first line, which
        # shifted every column by one and truncated the first path by a char.
        for line in result["stdout"].splitlines():
            if line.strip():
                status = line[:2].strip()
                path = line[3:]
                files.append({"status": status, "file": path})
        return {"files": files, "clean": len(files) == 0}

    async def log(self, limit: int = 10) -> list[GitCommit]:
        """
        Log.

        Args:
            limit (int): maximum number of items to return. Defaults to ``10``.

        Returns:
            list[GitCommit]: a sequence of GitCommit entries (empty when there is nothing to
                report).

        Note:
            Coroutine - must be awaited.
        """
        result = await self._run("log", f"-{limit}", "--format=%H|%an|%ai|%s")
        commits = []
        for line in result["stdout"].strip().split("\n"):
            if line:
                parts = line.split("|", 3)
                if len(parts) >= 4:
                    commits.append(
                        GitCommit(
                            hash=parts[0],
                            author=parts[1],
                            date=parts[2],
                            message=parts[3],
                        )
                    )
        return commits

    async def diff(self, file_path: str = None) -> str:
        """
        Diff.

        Args:
            file_path (str): path of the file to operate on. Defaults to ``None``.

        Returns:
            str: the rendered string.

        Note:
            Coroutine - must be awaited.
        """
        args = ["diff"]
        if file_path:
            args.append(file_path)
        result = await self._run(*args)
        return result["stdout"]

    async def add(self, files: list[str] = None) -> bool:
        """
        Add.

        Args:
            files (list[str]): collection of files. Defaults to ``None``.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        result = await self._run("add", *(files or ["."]))
        return result["returncode"] == 0

    async def commit(self, message: str) -> bool:
        """
        Commit.

        Args:
            message (str): message to process.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        result = await self._run("commit", "-m", message)
        return result["returncode"] == 0

    async def push(self, remote: str = "origin", branch: str = "main") -> bool:
        """
        Push.

        Args:
            remote (str): remote string. Defaults to ``'origin'``.
            branch (str): branch string. Defaults to ``'main'``.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        result = await self._run("push", remote, branch)
        return result["returncode"] == 0

    async def pull(self, remote: str = "origin", branch: str = "main") -> bool:
        """
        Pull.

        Args:
            remote (str): remote string. Defaults to ``'origin'``.
            branch (str): branch string. Defaults to ``'main'``.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        result = await self._run("pull", remote, branch)
        return result["returncode"] == 0

    async def branch(self) -> list[str]:
        """
        Branch.

        Returns:
            list[str]: a sequence of str entries (empty when there is nothing to report).

        Note:
            Coroutine - must be awaited.
        """
        result = await self._run("branch", "--format=%(refname:short)")
        return [b.strip() for b in result["stdout"].strip().split("\n") if b.strip()]

    async def checkout(self, branch: str) -> bool:
        """
        Checkout.

        Args:
            branch (str): branch string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        result = await self._run("checkout", branch)
        return result["returncode"] == 0

    async def create_branch(self, branch: str) -> bool:
        """
        Create branch.

        Args:
            branch (str): branch string.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        result = await self._run("checkout", "-b", branch)
        return result["returncode"] == 0

    async def stash(self) -> bool:
        """
        Stash.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        result = await self._run("stash")
        return result["returncode"] == 0

    async def stash_pop(self) -> bool:
        """
        Stash pop.

        Returns:
            bool: ``True`` when the operation succeeds, otherwise ``False``.

        Note:
            Coroutine - must be awaited.
        """
        result = await self._run("stash", "pop")
        return result["returncode"] == 0

    async def blame(self, file_path: str) -> str:
        """
        Blame.

        Args:
            file_path (str): path of the file to operate on.

        Returns:
            str: the rendered string.

        Note:
            Coroutine - must be awaited.
        """
        result = await self._run("blame", file_path)
        return result["stdout"]
