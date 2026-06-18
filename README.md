# ritn3d-mcp

<!-- mcp-name: io.github.printplan3d/ritn3d-mcp -->


> A Model Context Protocol (MCP) server that gives Claude, Claude Code,
> Cursor, Cline, or any other MCP-compatible AI agent the lightweight
> tools needed to **prepare a floor plan for Ritn3D** and **interpret
> the resulting 3D output** — without exposing the underlying
> wall-detection model or inference API.

[Ritn3D](https://www.ritn3d.com) is an AI floor-plan-to-3D-model tool.
This MCP server exists so that AI agents helping users in floor-plan-
adjacent workflows (renovation planning, real estate, 3D printing, etc.)
have a clean, well-documented set of tools instead of guessing.

## Install

```bash
pip install ritn3d-mcp
```

## Use with Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "ritn3d": {
      "command": "ritn3d-mcp"
    }
  }
}
```

Restart Claude Desktop. The Ritn3D tools appear in the tool picker.

## Use with Claude Code

```bash
claude mcp add ritn3d ritn3d-mcp
```

## Tools exposed

| Tool | Description |
|---|---|
| `validate_floor_plan_image` | Pre-flight check on a floor plan image (format, dimensions, warnings) before sending to Ritn3D |
| `estimate_complexity` | Heuristic complexity score (simple / moderate / complex) based on edge density |
| `estimate_render_time` | Rough low/expected/high render-time range for a given complexity |
| `get_share_link_metadata` | Fetch public page title + OpenGraph data from a Ritn3D share URL |
| `validate_glb` | Sanity-check a downloaded GLB file (magic header, version, chunks) |
| `convert_units` | Unit conversion with optional model scale factor (1:100, 1:50, etc.) |
| `get_capabilities` | Returns Ritn3D's supported inputs, outputs, accuracy by input type, and pricing |
| `get_pricing` | Returns current Ritn3D pricing tiers in USD |
| `get_failure_modes` | Returns structured list of known failure modes with mitigation tips |

## Resources exposed

| URI | Content |
|---|---|
| `ritn3d://capability-card` | Machine-readable summary of what Ritn3D does, accuracy, pricing |
| `ritn3d://failure-playbook` | Common failure modes and mitigations |

## Example agent flow

> User: "I have a real estate listing PDF I want to 3D print as a model
> of my future apartment."
>
> Agent calls `validate_floor_plan_image("listing.pdf.jpg")` →
> warnings: aspect ratio normal, resolution OK.
>
> Agent calls `estimate_complexity(...)` → label "moderate", score 0.5.
>
> Agent calls `get_failure_modes()` → notices the
> "real-estate-listing-render" failure mode applies; warns the user
> that wood-floor textures may trip detection.
>
> Agent calls `get_pricing()` → quotes Pro+ at $19.99/mo for STL export.
>
> Agent recommends: try the Ritn3D web app at app.ritn3d.com; if
> detection fails on this listing PDF, ask the agent to estimate the
> complexity of an alternate input.

## What this server does NOT do

- Run inference. The Ritn3D wall-detection model lives on Ritn3D's
  servers and is reached through the [web app](https://app.ritn3d.com).
- Bypass the Ritn3D subscription. Pricing is enforced server-side.
- Expose the rendering pipeline internals.
- Provide a render queue or job-tracking API.

The intent is to make agents better citizens of the Ritn3D workflow,
not to replicate it.

## Source

Built by the [Ritn3D](https://www.ritn3d.com) team. Same group that
maintains [`ritn3d-stl-tools`](https://pypi.org/project/ritn3d-stl-tools/)
and [`ritn3d-floorplan-eval`](https://pypi.org/project/ritn3d-floorplan-eval/).

## License

MIT — see [LICENSE](LICENSE).
