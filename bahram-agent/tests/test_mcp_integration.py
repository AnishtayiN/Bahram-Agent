"""Model Context Protocol client, exercised against a real child process.

``Agent._init_mcp_tools`` used to be a no-op that looked like it worked: it
passed a config dict to ``MCPClient.connect`` (which takes a *server name*),
awaited the synchronous ``list_tools()``, and then called ``.get()`` on the
strings it returned.  Every error was swallowed by a bare ``except``, so no
MCP server ever contributed a tool.

The tests below run a genuine MCP server - a small script that speaks JSON-RPC
over stdio - as a subprocess and drive the real client against it over a real
pipe.  No part of ``bahram.mcp`` is mocked.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from bahram.core.agent import _MCPToolAdapter
from bahram.mcp.client import MCPClient, MCPServerConfig, MCPTool

# A minimal but protocol-correct MCP server: answers initialize, tools/list and
# tools/call, one JSON-RPC message per line.
FAKE_SERVER = textwrap.dedent(
    """
    import json, sys

    TOOLS = [
        {
            "name": "echo",
            "description": "Echo the message back",
            "inputSchema": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
        },
        {
            "name": "add",
            "description": "Add two numbers",
            "inputSchema": {
                "type": "object",
                "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            },
        },
    ]

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request = json.loads(line)
        method = request.get("method")
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "serverInfo": {"name": "fake"},
            }
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = request.get("params", {})
            name = params.get("name")
            args = params.get("arguments", {})
            if name == "echo":
                text = args.get("message", "")
            elif name == "add":
                text = str(args.get("a", 0) + args.get("b", 0))
            else:
                text = "unknown tool"
            result = {"content": [{"type": "text", "text": text}]}
        else:
            error = {"code": -32601, "message": "method not found"}
            out = {"jsonrpc": "2.0", "id": request.get("id"), "error": error}
            sys.stdout.write(json.dumps(out) + "\\n")
            sys.stdout.flush()
            continue
        out = {"jsonrpc": "2.0", "id": request.get("id"), "result": result}
        sys.stdout.write(json.dumps(out) + "\\n")
        sys.stdout.flush()
    """
)


@pytest.fixture
def server_path(tmp_path: Path) -> Path:
    script = tmp_path / "fake_mcp_server.py"
    script.write_text(FAKE_SERVER)
    return script


@pytest.fixture
async def client(server_path: Path):
    instance = MCPClient()
    instance.servers["fake"] = MCPServerConfig(
        name="fake", type="stdio", command=[sys.executable, str(server_path)]
    )
    assert await instance.connect("fake") is True
    yield instance
    await instance.disconnect_all()


# ---------------------------------------------------------------------------
# client
# ---------------------------------------------------------------------------
class TestMCPClient:
    async def test_connect_discovers_tools(self, client: MCPClient):
        assert set(client.tools) == {"fake:echo", "fake:add"}

    async def test_discovered_tools_carry_schema_and_server(self, client: MCPClient):
        tool = client.tools["fake:echo"]
        assert isinstance(tool, MCPTool)
        assert tool.description == "Echo the message back"
        assert tool.server_name == "fake"
        assert tool.input_schema["properties"]["message"]["type"] == "string"

    async def test_call_tool_returns_the_text_content(self, client: MCPClient):
        assert await client.call_tool("fake:echo", {"message": "hello mcp"}) == "hello mcp"
        assert await client.call_tool("fake:add", {"a": 2, "b": 40}) == "42"

    async def test_call_unknown_tool_is_reported_not_raised(self, client: MCPClient):
        assert "Tool not found" in await client.call_tool("fake:nope", {})

    async def test_call_tool_on_a_disconnected_server(self, client: MCPClient):
        await client.disconnect("fake")
        assert "not found" in await client.call_tool("fake:echo", {})

    async def test_get_tools_schema_is_openai_shaped(self, client: MCPClient):
        schemas = client.get_tools_schema()
        assert len(schemas) == 2
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"] == "fake:echo"

    def test_list_servers_and_tools(self, client: MCPClient):
        assert client.list_servers() == ["fake"]
        assert sorted(client.list_tools()) == ["fake:add", "fake:echo"]

    async def test_connect_unknown_server_returns_false(self):
        assert await MCPClient().connect("nope") is False

    async def test_connect_disabled_server_returns_false(self):
        instance = MCPClient()
        instance.servers["off"] = MCPServerConfig(name="off", enabled=False)
        assert await instance.connect("off") is False

    async def test_connect_unknown_type_returns_false(self):
        instance = MCPClient()
        instance.servers["weird"] = MCPServerConfig(name="weird", type="carrier-pigeon")
        assert await instance.connect("weird") is False

    async def test_connect_without_a_command_returns_false(self):
        instance = MCPClient()
        instance.servers["empty"] = MCPServerConfig(name="empty")
        assert await instance.connect("empty") is False

    async def test_connect_failure_is_swallowed(self):
        instance = MCPClient()
        instance.servers["broken"] = MCPServerConfig(name="broken", command=["/no/such/binary"])
        assert await instance.connect("broken") is False

    async def test_http_connect_against_a_real_server(self):
        """Drive _connect_http against an actual HTTP endpoint."""
        http_server = textwrap.dedent(
            """
            import json
            from http.server import BaseHTTPRequestHandler, HTTPServer

            class Handler(BaseHTTPRequestHandler):
                def do_POST(self):
                    body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                    if body["method"] == "initialize":
                        result = {"protocolVersion": "2024-11-05", "capabilities": {}}
                    else:
                        result = {
                            "tools": [{"name": "remote", "description": "d", "inputSchema": {}}]
                        }
                    out = {"jsonrpc": "2.0", "id": body["id"], "result": result}
                    payload = json.dumps(out).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)

                def log_message(self, *args):
                    pass

            server = HTTPServer(("127.0.0.1", 0), Handler)
            print(server.server_address[1], flush=True)
            server.handle_request()
            server.handle_request()
            """
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", http_server], stdout=subprocess.PIPE, text=True
        )
        try:
            port = int(proc.stdout.readline().strip())
            instance = MCPClient()
            instance.servers["http"] = MCPServerConfig(
                name="http", type="http", url=f"http://127.0.0.1:{port}/mcp"
            )
            assert await instance.connect("http") is True
            assert instance.list_tools() == ["http:remote"]
        finally:
            proc.kill()
            proc.wait()

    async def test_http_connect_failure_is_swallowed(self):
        instance = MCPClient()
        instance.servers["http"] = MCPServerConfig(
            name="http", type="http", url="http://127.0.0.1:1/mcp", timeout=1
        )
        assert await instance.connect("http") is False

    def test_load_config_reads_yaml(self, tmp_path: Path):
        cfg = tmp_path / "mcp.yaml"
        cfg.write_text(
            "mcp_servers:\n"
            "  files:\n"
            "    type: stdio\n"
            "    command: ['/usr/bin/env', 'true']\n"
            "    enabled: true\n"
            "    timeout: 5\n"
        )
        instance = MCPClient()
        instance.load_config(str(cfg))
        assert instance.list_servers() == ["files"]
        assert instance.servers["files"].command == ["/usr/bin/env", "true"]
        assert instance.servers["files"].timeout == 5

    def test_load_config_reads_json(self, tmp_path: Path):
        cfg = tmp_path / "mcp.json"
        cfg.write_text(json.dumps({"mcp_servers": {"j": {"type": "http", "url": "http://x"}}}))
        instance = MCPClient()
        instance.load_config(str(cfg))
        assert instance.servers["j"].type == "http"

    def test_load_config_ignores_a_missing_file(self, tmp_path: Path):
        instance = MCPClient()
        instance.load_config(str(tmp_path / "nope.yaml"))
        assert instance.list_servers() == []

    def test_load_config_ignores_a_file_without_servers(self, tmp_path: Path):
        cfg = tmp_path / "mcp.yaml"
        cfg.write_text("something_else: 1\n")
        instance = MCPClient()
        instance.load_config(str(cfg))
        assert instance.list_servers() == []

    async def test_disconnect_all_is_idempotent(self, client: MCPClient):
        await client.disconnect_all()
        await client.disconnect_all()
        assert client.list_tools() == []

    async def test_send_without_a_connection_is_a_noop(self):
        instance = MCPClient()
        await instance._send_message("ghost", {"jsonrpc": "2.0"})
        assert await instance._receive_message("ghost") is None


# ---------------------------------------------------------------------------
# MCP server (the other side of the protocol)
# ---------------------------------------------------------------------------
class TestMCPServer:
    async def test_register_and_list_tools(self):
        from bahram.mcp.server import MCPServer

        server = MCPServer(name="test-server")

        async def greet(name: str) -> str:
            return f"hi {name}"

        server.register_tool("greet", "Greet someone", {"type": "object"}, greet)

        response = await server.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        )
        names = [t["name"] for t in response["result"]["tools"]]
        assert names == ["greet"]

    async def test_initialize_response(self):
        from bahram.mcp.server import MCPServer

        response = await MCPServer().handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        assert response["result"]["serverInfo"]["name"] == "bahram-agent"

    async def test_call_tool_dispatch(self):
        from bahram.mcp.server import MCPServer

        server = MCPServer()

        async def double(x: int) -> str:
            return str(x * 2)

        server.register_tool("double", "Double a number", {"type": "object"}, double)
        response = await server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "double", "arguments": {"x": 21}},
            }
        )
        assert response["result"]["content"][0]["text"] == "42"

    async def test_call_unknown_tool_returns_an_error(self):
        from bahram.mcp.server import MCPServer

        response = await MCPServer().handle_request(
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "nope"}}
        )
        assert "error" in response

    async def test_unknown_method_returns_an_error(self):
        from bahram.mcp.server import MCPServer

        response = await MCPServer().handle_request(
            {"jsonrpc": "2.0", "id": 4, "method": "nope", "params": {}}
        )
        assert "error" in response


# ---------------------------------------------------------------------------
# the adapter Agent registers
# ---------------------------------------------------------------------------
class TestMCPToolAdapter:
    async def test_schema_is_prefixed_and_typed(self):
        adapter = _MCPToolAdapter(
            None,
            {
                "name": "echo",
                "description": "Echo",
                "inputSchema": {"type": "object", "properties": {"m": {"type": "string"}}},
            },
        )
        schema = adapter.schema()
        assert schema["name"] == "mcp_echo"
        assert schema["parameters"]["properties"]["m"]["type"] == "string"

    async def test_execute_calls_the_qualified_name(self, client: MCPClient):
        adapter = _MCPToolAdapter(
            client,
            {"name": "echo", "description": "Echo", "inputSchema": {}},
            call_name="fake:echo",
        )
        assert await adapter.execute(message="routed correctly") == "routed correctly"

    async def test_execute_falls_back_to_the_bare_name(self, client: MCPClient):
        """Without call_name the qualified key is used, which the client rejects."""
        adapter = _MCPToolAdapter(
            client, {"name": "echo", "description": "Echo", "inputSchema": {}}
        )
        assert "not found" in await adapter.execute(message="x")


# ---------------------------------------------------------------------------
# Agent wiring: an MCP server must actually contribute tools
# ---------------------------------------------------------------------------
class TestAgentMcpWiring:
    async def test_agent_registers_tools_from_a_real_server(self, server_path: Path):
        from bahram.core.agent import Agent
        from bahram.core.config import Config

        config = Config()
        config.memory.database = ":memory:"
        agent = Agent(config=config)
        await agent.start()

        class McpConfig:
            servers = [
                {
                    "name": "fake",
                    "type": "stdio",
                    "command": [sys.executable, str(server_path)],
                }
            ]

        agent.config.mcp = McpConfig()
        before = set(agent.engine.tools)
        await agent._init_mcp_tools()

        added = set(agent.engine.tools) - before
        assert added == {"mcp_echo", "mcp_add"}, f"MCP tools were not registered: {added}"

    async def test_registered_mcp_tool_executes(self, server_path: Path):
        from bahram.core.agent import Agent
        from bahram.core.config import Config

        config = Config()
        config.memory.database = ":memory:"
        agent = Agent(config=config)
        await agent.start()

        class McpConfig:
            servers = [
                {"name": "fake", "command": [sys.executable, str(server_path)]},
            ]

        agent.config.mcp = McpConfig()
        await agent._init_mcp_tools()

        adapter = agent.engine.tools["mcp_add"]
        assert await adapter.execute(a=1, b=2) == "3"
        await agent.stop()

    async def test_a_broken_server_does_not_break_startup(self):
        from bahram.core.agent import Agent
        from bahram.core.config import Config

        config = Config()
        config.memory.database = ":memory:"
        agent = Agent(config=config)
        await agent.start()

        class McpConfig:
            servers = [{"name": "broken", "command": ["/no/such/binary"]}, {"no": "name"}]

        agent.config.mcp = McpConfig()
        await agent._init_mcp_tools()
        assert not [n for n in agent.engine.tools if n.startswith("mcp_")]

    async def test_command_given_as_a_string_is_split(self, server_path: Path):
        from bahram.core.agent import Agent
        from bahram.core.config import Config

        config = Config()
        config.memory.database = ":memory:"
        agent = Agent(config=config)
        await agent.start()

        class McpConfig:
            servers = [{"name": "fake", "command": f"{sys.executable} {server_path}"}]

        agent.config.mcp = McpConfig()
        await agent._init_mcp_tools()
        assert "mcp_echo" in agent.engine.tools
