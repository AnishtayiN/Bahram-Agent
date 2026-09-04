from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LSPServer:
    name: str
    command: str
    language: str
    process: Any = None


class LSPTool:
    def __init__(self) -> None:
        self._servers: dict[str, LSPServer] = {}
        self._initialized: dict[str, bool] = {}

    def register_server(
        self,
        name: str,
        command: str,
        language: str,
    ) -> None:
        self._servers[name] = LSPServer(
            name=name,
            command=command,
            language=language,
        )

    async def start_server(self, name: str) -> bool:
        server = self._servers.get(name)
        if not server:
            return False

        try:
            proc = await asyncio.create_subprocess_shell(
                server.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            server.process = proc
            self._initialized[name] = True
            return True

        except Exception as e:
            logger.error(f"Failed to start LSP server {name}: {e}")
            return False

    async def stop_server(self, name: str) -> bool:
        server = self._servers.get(name)
        if not server or not server.process:
            return False

        try:
            server.process.terminate()
            await server.process.wait()
            server.process = None
            self._initialized[name] = False
            return True
        except Exception as e:
            logger.error(f"Failed to stop LSP server {name}: {e}")
            return False

    async def completion(
        self,
        server_name: str,
        file_path: str,
        line: int,
        character: int,
    ) -> list[dict]:
        server = self._servers.get(server_name)
        if not server or not server.process:
            return []

        try:
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "textDocument/completion",
                "params": {
                    "textDocument": {"uri": f"file://{file_path}"},
                    "position": {"line": line, "character": character},
                },
            }

            message = f"Content-Length: {len(json.dumps(request))}\r\n\r\n{json.dumps(request)}"
            server.process.stdin.write(message.encode())
            await server.process.stdin.drain()

            response = await asyncio.wait_for(
                server.process.stdout.readline(),
                timeout=5.0,
            )

            return json.loads(response.decode().split("\r\n\r\n")[-1]).get("result", [])

        except Exception as e:
            logger.warning(f"Completion failed: {e}")
            return []

    def is_running(self, name: str) -> bool:
        return self._initialized.get(name, False)
