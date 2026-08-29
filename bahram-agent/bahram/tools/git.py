from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class GitCommit:
    ""

    hash: str
    author: str
    date: str
    message: str

class GitTool:
    ""

    def __init__(self, repo_path: str = ".") -> None:
        self.repo_path = repo_path

    async def _run(self, command: str) -> dict[str, Any]:
        ""
        proc = await asyncio.create_subprocess_shell(
            f"git -C {self.repo_path} {command}",
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
        ""
        result = await self._run("status --porcelain")
        files = []
        for line in result["stdout"].strip().split("\n"):
            if line:
                status = line[:2].strip()
                file = line[3:]
                files.append({"status": status, "file": file})
        return {"files": files, "clean": len(files) == 0}

    async def log(self, limit: int = 10) -> list[GitCommit]:
        ""
        result = await self._run(f"log --oneline -{limit} --format=%H|%an|%ai|%s")
        commits = []
        for line in result["stdout"].strip().split("\n"):
            if line:
                parts = line.split("|", 3)
                if len(parts) >= 4:
                    commits.append(GitCommit(
                        hash=parts[0],
                        author=parts[1],
                        date=parts[2],
                        message=parts[3],
                    ))
        return commits

    async def diff(self, file_path: str = None) -> str:
        ""
        cmd = "diff"
        if file_path:
            cmd += f" {file_path}"
        result = await self._run(cmd)
        return result["stdout"]

    async def add(self, files: list[str] = None) -> bool:
        ""
        cmd = "add"
        if files:
            cmd += " " + " ".join(files)
        else:
            cmd += " ."
        result = await self._run(cmd)
        return result["returncode"] == 0

    async def commit(self, message: str) -> bool:
        ""
        result = await self._run(f'commit -m "{message}"')
        return result["returncode"] == 0

    async def push(self, remote: str = "origin", branch: str = "main") -> bool:
        ""
        result = await self._run(f"push {remote} {branch}")
        return result["returncode"] == 0

    async def pull(self, remote: str = "origin", branch: str = "main") -> bool:
        ""
        result = await self._run(f"pull {remote} {branch}")
        return result["returncode"] == 0

    async def branch(self) -> list[str]:
        ""
        result = await self._run("branch --format=%(refname:short)")
        return [b.strip() for b in result["stdout"].strip().split("\n") if b.strip()]

    async def checkout(self, branch: str) -> bool:
        ""
        result = await self._run(f"checkout {branch}")
        return result["returncode"] == 0

    async def create_branch(self, branch: str) -> bool:
        ""
        result = await self._run(f"checkout -b {branch}")
        return result["returncode"] == 0

    async def stash(self) -> bool:
        ""
        result = await self._run("stash")
        return result["returncode"] == 0

    async def stash_pop(self) -> bool:
        ""
        result = await self._run("stash pop")
        return result["returncode"] == 0

    async def blame(self, file_path: str) -> str:
        ""
        result = await self._run(f"blame {file_path}")
        return result["stdout"]
