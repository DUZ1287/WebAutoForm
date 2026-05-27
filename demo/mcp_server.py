"""MCP (Model Context Protocol) server for web-auto-form.

Exposes web_auto_form as a tool that AI agents (Claude Desktop, Cursor, etc.)
can discover and invoke via MCP.

Setup:
    1. pip install web-auto-form mcp
    2. Add to claude_desktop_config.json:
       {
         "mcpServers": {
           "web-auto-form": {
             "command": "python",
             "args": ["demo/mcp_server.py"]
           }
         }
       }

Usage:
    python demo/mcp_server.py

The server reads the JSON tool schema from web_auto_form_tool.json
and the system prompt from SYSTEM_PROMPT.md, then registers them
as an MCP tool.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from web_auto_form import run

# ── MCP Server Implementation ──────────────────────────────────────────────
# Uses the official MCP Python SDK when available, falls back to stdio JSON-RPC.

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool

    HAS_MCP = True
except ImportError:
    HAS_MCP = False

# ── Schema cache ─────────────────────────────────────────────────────────
_schema_cache: dict | None = None


def load_tool_schema() -> dict:
    """Load the web_auto_form tool schema (cached after first read)."""
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache
    schema_path = PROJECT_ROOT / "web_auto_form_tool.json"
    with open(schema_path, encoding="utf-8") as f:
        _schema_cache = json.load(f)
    return _schema_cache


def load_system_prompt() -> str:
    """Load the system prompt for AI agent integration."""
    prompt_path = PROJECT_ROOT / "SYSTEM_PROMPT.md"
    with open(prompt_path, encoding="utf-8") as f:
        return f.read()


def execute_config(config: dict) -> dict:
    """Execute a web-auto-form config and return the result."""
    return run(config)


# ── MCP Mode ────────────────────────────────────────────────────────────────


def run_mcp_server() -> None:
    """Run as an MCP server using the official SDK."""
    if not HAS_MCP:
        print("MCP SDK not installed. Install with: pip install mcp", file=sys.stderr)
        print("Falling back to stdio JSON-RPC mode.", file=sys.stderr)
        run_stdio_server()
        return

    tool_schema = load_tool_schema()

    server = Server("web-auto-form")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=tool_schema["name"],
                description=tool_schema["description"],
                inputSchema=tool_schema["input_schema"],
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name != "web_auto_form":
            raise ValueError(f"Unknown tool: {name}")

        result = execute_config(arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    import asyncio

    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(main())


# ── Stdio JSON-RPC Fallback ─────────────────────────────────────────────────


def run_stdio_server() -> None:
    """Minimal stdio JSON-RPC server for environments without the MCP SDK."""
    import sys

    tool_schema = load_tool_schema()

    print(f"web-auto-form MCP server ready (stdio mode)", file=sys.stderr)
    print(f"Tool: {tool_schema['name']}", file=sys.stderr)
    print(f"Awaiting JSON-RPC requests on stdin...", file=sys.stderr)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = request.get("method", "")

        if method == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "tools": [
                        {
                            "name": tool_schema["name"],
                            "description": tool_schema["description"],
                            "inputSchema": tool_schema["input_schema"],
                        }
                    ]
                },
            }
            print(json.dumps(response))
            sys.stdout.flush()

        elif method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            if tool_name != "web_auto_form":
                response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                }
            else:
                try:
                    result = execute_config(arguments)
                    response = {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result, indent=2, ensure_ascii=False),
                                }
                            ]
                        },
                    }
                except Exception as e:
                    response = {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "error": {"code": -32000, "message": str(e)},
                    }

            print(json.dumps(response))
            sys.stdout.flush()


# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if HAS_MCP:
        run_mcp_server()
    else:
        run_stdio_server()
