from __future__ import annotations

import asyncio
import json
import logging
import sys
from collections.abc import Callable
from typing import Any, Optional

logger = logging.getLogger(__name__)

class MCPServer:

    def __init__(self, name: str = "bahram-agent") -> None:
        self.name = name
        self.tools: dict[str, dict] = {}
        self._tool_handlers: dict[str, Callable] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable,
    ) -> None:
        self.tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
        }
        self._tool_handlers[name] = handler

    async def handle_request(self, request: dict) -> dict:
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "initialize":
            return self._handle_initialize(request_id, params)
        elif method == "tools/list":
            return self._handle_list_tools(request_id)
        elif method == "tools/call":
            return await self._handle_call_tool(request_id, params)
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

    def _handle_initialize(self, request_id: int, params: dict) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": self.name,
                    "version": "1.0.0",
                },
            },
        }

    def _handle_list_tools(self, request_id: int) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": list(self.tools.values()),
            },
        }

    async def _handle_call_tool(self, request_id: int, params: dict) -> dict:
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self.tools:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": f"Tool not found: {tool_name}"},
            }

        try:
            handler = self._tool_handlers[tool_name]
            result = await handler(**arguments)

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": str(result)}],
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": str(e)},
            }

    async def run_stdio(self) -> None:
        logger.info("MCP server started on stdio")

        try:
            while True:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                if not line:
                    break

                try:
                    request = json.loads(line.strip())
                    response = await self.handle_request(request)
                    print(json.dumps(response), flush=True)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")

        except KeyboardInterrupt:
            logger.info("MCP server stopped")

    async def run_http(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        try:
            from aiohttp import web

            async def handle_mcp(request: web.Request) -> web.Response:
                data = await request.json()
                response = await self.handle_request(data)
                return web.json_response(response)

            app = web.Application()
            app.router.add_post("/mcp", handle_mcp)

            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, host, port)
            await site.start()

            logger.info(f"MCP server started on http://{host}:{port}/mcp")

            await asyncio.Event().wait()

        except ImportError:
            logger.error("aiohttp not installed. Install with: pip install aiohttp")
        except Exception as e:
            logger.error(f"Failed to start HTTP server: {e}")
