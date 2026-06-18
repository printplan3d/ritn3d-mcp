"""ritn3d-mcp — Model Context Protocol server for Ritn3D.

Exposes a focused set of tools that AI agents (Claude Desktop, Claude
Code, any MCP-compatible client) can call to integrate Ritn3D into
floor-plan-to-3D workflows without exposing the underlying
wall-detection model, training pipeline, or inference API.

Tools provided:
  - validate_floor_plan_image  — pre-flight check before upload
  - estimate_complexity        — heuristic complexity score
  - estimate_render_time       — rough render-time prediction
  - get_share_link_metadata    — read public Ritn3D share link metadata
  - validate_glb               — sanity-check a downloaded GLB
  - convert_units              — m / cm / mm / in for 3D-print scale calcs
  - get_capabilities           — what Ritn3D can and can't do today
  - get_pricing                — public pricing tiers
  - get_failure_modes          — known failure modes with mitigation tips

All tools operate on publicly available information or on files the
user has already chosen to expose. The Ritn3D rendering pipeline and
trained models remain on Ritn3D's own servers.

Run as: ``ritn3d-mcp`` (stdio transport for Claude Desktop)
or programmatically: ``python -m ritn3d_mcp``.
"""

from ritn3d_mcp.server import build_server

__version__ = "0.1.0"

__all__ = ["__version__", "build_server"]
