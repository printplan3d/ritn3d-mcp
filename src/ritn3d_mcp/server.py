"""MCP server wiring — registers tools and resources.

This module builds the actual `mcp.server.Server` instance and binds
each tool. Tool implementations live in ``tools.py``; resources in
``resources.py``. Keeping wiring separate from logic makes the server
easy to embed in tests and easy to extend with new tools later.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server import Server
from mcp.types import Resource, TextContent, Tool

from ritn3d_mcp.resources import RESOURCE_REGISTRY
from ritn3d_mcp.tools import TOOL_REGISTRY, ToolError


def build_server(name: str = "ritn3d-mcp") -> Server:
    """Construct an MCP `Server` with every Ritn3D tool registered.

    Splitting this out into a builder makes it trivial to embed the
    server in tests (instantiate, call tools directly without spawning
    a real transport) or to compose multiple servers in a single process.
    """
    server: Server = Server(name)

    # ── Tools ────────────────────────────────────────────────────────
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=name,
                description=spec.description,
                inputSchema=spec.input_schema,
            )
            for name, spec in TOOL_REGISTRY.items()
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        spec = TOOL_REGISTRY.get(name)
        if spec is None:
            raise ToolError(f"Unknown tool: {name!r}")
        result = await spec.handler(**(arguments or {}))
        # Always serialize to JSON text — MCP clients can parse it. We
        # do not emit binary content from this server.
        if isinstance(result, str):
            payload = result
        else:
            payload = json.dumps(result, indent=2, default=str)
        return [TextContent(type="text", text=payload)]

    # ── Resources ────────────────────────────────────────────────────
    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri=res.uri,
                name=res.name,
                description=res.description,
                mimeType=res.mime_type,
            )
            for res in RESOURCE_REGISTRY
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        for res in RESOURCE_REGISTRY:
            if res.uri == uri:
                return res.read()
        raise ToolError(f"Resource not found: {uri!r}")

    return server
