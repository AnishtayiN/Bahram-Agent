from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class MCPServerConfig:

    name: str
    type: str = "stdio"
    command: list[str] = field(default_factory=list)
    url: str = ""
    env: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    timeout: int = 30

@dataclass
class MCPTool:

    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str

class MCPClient:

    def __init__(self) -> None:
        self.servers: dict[str, MCPServerConfig] = {}
        self.tools: dict[str, MCPTool] = {}
        self._connections: dict[str, Any] = {}

    def load_config(self, config_path: str) -> None:
        path = Path(config_path)
        if not path.exists():
            return

        try:
            import yaml
            with open(path) as f:
                data = yaml.safe_load(f)
        except ImportError:
            with open(path) as f:
                data = json.load(f)

        if "mcp_servers" in data:
            for name, server_data in data["mcp_servers"].items():
                self.servers[name] = MCPServerConfig(
                    name=name,
                    type=server_data.get("type", "stdio"),
                    command=server_data.get("command", []),
                    url=server_data.get("url", ""),
                    env=server_data.get("env", {}),
                    headers=server_data.get("headers", {}),
                    enabled=server_data.get("enabled", True),
                    timeout=server_data.get("timeout", 30),
                )

    async def connect(self, server_name: str) -> bool:
        config = self.servers.get(server_name)
        if not config:
            logger.error(f"Server not found: {server_name}")
            return False

        if not config.enabled:
            logger.info(f"Server disabled: {server_name}")
            return False

        try:
            if config.type == "stdio":
                return await self._connect_stdio(config)
            elif config.type == "http":
                return await self._connect_http(config)
            else:
                logger.error(f"Unknown server type: {config.type}")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to {server_name}: {e}")
            return False

    async def _connect_stdio(self, config: MCPServerConfig) -> bool:
        if not config.command:
            logger.error(f"No command specified for {config.name}")
            return False

        try:
            process = await asyncio.create_subprocess_exec(
                *config.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**dict(__import__("os").environ), **config.env},
            )

            self._connections[config.name] = {
                "process": process,
                "type": "stdio",
            }

            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "bahram-agent",
                        "version": "1.0.0",
                    },
                },
            }

            await self._send_message(config.name, init_request)
            response = await self._receive_message(config.name)

            if response and "result" in response:

                tools_request = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {},
                }
                await self._send_message(config.name, tools_request)
                tools_response = await self._receive_message(config.name)

                if tools_response and "result" in tools_response:
                    for tool in tools_response["result"].get("tools", []):
                        mcp_tool = MCPTool(
                            name=tool["name"],
                            description=tool.get("description", ""),
                            input_schema=tool.get("inputSchema", {}),
                            server_name=config.name,
                        )
                        self.tools[f"{config.name}:{tool['name']}"] = mcp_tool

                logger.info(f"Connected to MCP server: {config.name}")
                return True

            return False

        except Exception as e:
            logger.error(f"Failed to connect stdio server: {e}")
            return False

    async def _connect_http(self, config: MCPServerConfig) -> bool:
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    config.url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {
                                "name": "bahram-agent",
                                "version": "1.0.0",
                            },
                        },
                    },
                    headers=config.headers,
                    timeout=config.timeout,
                )

                if response.status_code == 200:
                    self._connections[config.name] = {
                        "url": config.url,
                        "type": "http",
                        "headers": config.headers,
                    }

                    tools_response = await client.post(
                        config.url,
                        json={
                            "jsonrpc": "2.0",
                            "id": 2,
                            "method": "tools/list",
                            "params": {},
                        },
                        headers=config.headers,
                        timeout=config.timeout,
                    )

                    if tools_response.status_code == 200:
                        tools_data = tools_response.json()
                        for tool in tools_data.get("result", {}).get("tools", []):
                            mcp_tool = MCPTool(
                                name=tool["name"],
                                description=tool.get("description", ""),
                                input_schema=tool.get("inputSchema", {}),
                                server_name=config.name,
                            )
                            self.tools[f"{config.name}:{tool['name']}"] = mcp_tool

                    logger.info(f"Connected to HTTP MCP server: {config.name}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Failed to connect HTTP server: {e}")
            return False

    async def _send_message(self, server_name: str, message: dict) -> None:
        conn = self._connections.get(server_name)
        if not conn:
            return

        if conn["type"] == "stdio":
            process = conn["process"]
            data = json.dumps(message) + "\n"
            process.stdin.write(data.encode())
            await process.stdin.drain()

    async def _receive_message(self, server_name: str) -> Optional[dict]:
        conn = self._connections.get(server_name)
        if not conn:
            return None

        if conn["type"] == "stdio":
            process = conn["process"]
            try:
                line = await asyncio.wait_for(
                    process.stdout.readline(), timeout=30
                )
                if line:
                    return json.loads(line.decode())
            except asyncio.TimeoutError:
                logger.warning(f"Timeout receiving from {server_name}")

        return None

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        tool = self.tools.get(tool_name)
        if not tool:
            return f"Tool not found: {tool_name}"

        conn = self._connections.get(tool.server_name)
        if not conn:
            return f"Not connected to server: {tool.server_name}"

        try:
            request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": tool.name,
                    "arguments": arguments,
                },
            }

            await self._send_message(tool.server_name, request)
            response = await self._receive_message(tool.server_name)

            if response and "result" in response:
                content = response["result"].get("content", [])
                texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                return "\n".join(texts) if texts else "No content"
            elif response and "error" in response:
                return f"Error: {response['error'].get('message', 'Unknown error')}"

            return "No response"

        except Exception as e:
            return f"Error calling tool: {e}"

    async def disconnect(self, server_name: str) -> None:
        conn = self._connections.pop(server_name, None)
        if conn and conn["type"] == "stdio":
            process = conn.get("process")
            if process:
                process.terminate()
                await process.wait()

        self.tools = {k: v for k, v in self.tools.items() if v.server_name != server_name}

    async def disconnect_all(self) -> None:
        for server_name in list(self._connections.keys()):
            await self.disconnect(server_name)

    def get_tools_schema(self) -> list[dict[str, Any]]:
        schemas = []
        for name, tool in self.tools.items():
            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            })
        return schemas

    def list_servers(self) -> list[str]:
        return list(self.servers.keys())

    def list_tools(self) -> list[str]:
        return list(self.tools.keys())
