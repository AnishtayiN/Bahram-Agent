"""Real MCP fixture server for testing.

Exposes three tools:
1. echo - safe tool that returns input
2. dangerous_op - requires approval (simulates dangerous operation)
3. failing_tool - always fails (for error handling tests)

Runs as a stdio MCP server using JSON-RPC protocol.
"""

from __future__ import annotations

import json
import logging
import sys

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "2024-11-05"

TOOLS = [
    {
        "name": "echo",
        "description": "Echoes the input back. Safe tool, no approval needed.",
        "inputSchema": {
            "type": "object",
            "properties": {"message": {"type": "string", "description": "Message to echo"}},
            "required": ["message"],
        },
    },
    {
        "name": "dangerous_op",
        "description": "Performs a dangerous operation. Requires approval.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Dangerous action to perform"}
            },
            "required": ["action"],
        },
    },
    {
        "name": "failing_tool",
        "description": "Always fails with an error. For testing error handling.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def handle_initialize(request: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "test-mcp-server", "version": "1.0.0"},
        },
    }


def handle_tools_list(request: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "result": {"tools": TOOLS},
    }


def handle_tools_call(request: dict) -> dict:
    params = request.get("params", {})
    tool_name = params.get("name", "")
    arguments = params.get("arguments", {})

    if tool_name == "echo":
        result = arguments.get("message", "")
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "content": [{"type": "text", "text": result}],
                "isError": False,
            },
        }

    elif tool_name == "dangerous_op":
        action = arguments.get("action", "")
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "content": [{"type": "text", "text": f"Dangerous operation '{action}' executed"}],
                "isError": False,
            },
        }

    elif tool_name == "failing_tool":
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "content": [{"type": "text", "text": "Tool execution failed: simulated failure"}],
                "isError": True,
            },
        }

    else:
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
        }


def handle_request(request: dict) -> dict:
    method = request.get("method", "")
    if method == "initialize":
        return handle_initialize(request)
    elif method == "tools/list":
        return handle_tools_list(request)
    elif method == "tools/call":
        return handle_tools_call(request)
    elif method == "notifications/initialized":
        return {"jsonrpc": "2.0", "id": request.get("id"), "result": {}}
    else:
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }


def run_stdio():
    """Run the MCP server over stdio (JSON lines)."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    run_stdio()
