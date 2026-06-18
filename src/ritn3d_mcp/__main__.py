"""CLI entry point — ``ritn3d-mcp`` runs the server over stdio."""

from __future__ import annotations

import asyncio
import sys

from mcp.server.stdio import stdio_server

from ritn3d_mcp.server import build_server


async def _run() -> int:
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
    return 0


def main() -> int:
    """Synchronous CLI entry point."""
    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        sys.stderr.write("\nritn3d-mcp: shutting down\n")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
