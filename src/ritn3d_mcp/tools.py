"""Ritn3D MCP tools — each function is exposed to AI agents.

Every tool below works on public information or on user-provided
files. NONE call the Ritn3D inference API or expose the wall-
detection model. The intent is to give AI agents (Claude Desktop /
Claude Code / Cursor / Cline / any MCP client) the lightweight
helpers needed to PREPARE a floor plan for Ritn3D and INTERPRET
output GLBs — not to perform inference themselves.

Each tool registers a `ToolSpec` in `TOOL_REGISTRY`. The server
module reads the registry to expose tools to MCP clients. To add a
new tool, write the handler and append to the registry at module
load time.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

import httpx
from PIL import Image


# ── Error type ──────────────────────────────────────────────────────


class ToolError(RuntimeError):
    """Raised when a tool's preconditions are violated.

    The MCP server converts this into a structured error response
    that the AI agent can read and act on.
    """


# ── Tool registry plumbing ──────────────────────────────────────────


@dataclass(frozen=True)
class ToolSpec:
    """Declarative description of a tool MCP clients can call."""

    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Awaitable[Any]]


TOOL_REGISTRY: dict[str, ToolSpec] = {}


def _tool(name: str, *, description: str, input_schema: dict[str, Any]):
    """Decorator: register an async function as an MCP tool."""

    def decorator(fn: Callable[..., Awaitable[Any]]):
        TOOL_REGISTRY[name] = ToolSpec(
            description=description,
            input_schema=input_schema,
            handler=fn,
        )
        return fn

    return decorator


# ── Tool 1 — validate_floor_plan_image ──────────────────────────────


@_tool(
    "validate_floor_plan_image",
    description=(
        "Pre-flight check on a floor plan image before sending it to "
        "Ritn3D. Reports format, dimensions, file size, color mode, and "
        "heuristic warnings (too small, wrong aspect, low contrast). "
        "Use this before uploading via the Ritn3D web app or mobile app "
        "to catch obvious problems early."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Filesystem path to the floor plan image (JPG, PNG, BMP, TIFF, WebP).",
            }
        },
        "required": ["path"],
    },
)
async def validate_floor_plan_image(path: str) -> dict[str, Any]:
    p = Path(path).expanduser()
    if not p.exists():
        raise ToolError(f"File not found: {p}")
    if not p.is_file():
        raise ToolError(f"Path is not a file: {p}")

    size_bytes = p.stat().st_size
    warnings: list[str] = []
    try:
        with Image.open(p) as img:
            width, height = img.size
            mode = img.mode
            fmt = img.format
    except Exception as exc:
        raise ToolError(f"Could not decode as image: {exc}") from exc

    if width < 600 or height < 600:
        warnings.append(
            f"Image is small ({width}x{height}px). Ritn3D detection is "
            "more accurate above 800px on the shortest edge."
        )
    aspect = width / height if height else 0
    if aspect > 3 or aspect < 1 / 3:
        warnings.append(
            f"Unusual aspect ratio ({aspect:.2f}). Crop to the plan area; "
            "narrow strips around the floor plan add noise."
        )
    if mode not in ("RGB", "L", "RGBA"):
        warnings.append(
            f"Color mode {mode!r}. Most Ritn3D-friendly modes are RGB and "
            "grayscale (L). Convert before upload for best results."
        )
    if size_bytes > 20 * 1024 * 1024:
        warnings.append(
            "File is over 20 MB. Mobile uploads may be slow or rejected. "
            "Re-export at lower JPEG quality or scale down."
        )

    return {
        "ok": len(warnings) == 0,
        "path": str(p),
        "format": fmt,
        "width": width,
        "height": height,
        "mode": mode,
        "size_bytes": size_bytes,
        "warnings": warnings,
    }


# ── Tool 2 — estimate_complexity ────────────────────────────────────


@_tool(
    "estimate_complexity",
    description=(
        "Heuristic estimate of a floor plan's detection complexity. "
        "Reads basic image stats (resolution, brightness range, edge "
        "density) and returns a label (simple/moderate/complex) plus "
        "a numeric score. Useful for batch routing and for setting "
        "user expectations about how many corrections may be needed."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the floor plan image."}
        },
        "required": ["path"],
    },
)
async def estimate_complexity(path: str) -> dict[str, Any]:
    import numpy as np

    p = Path(path).expanduser()
    if not p.exists():
        raise ToolError(f"File not found: {p}")
    with Image.open(p) as img:
        gray = img.convert("L")
        arr = np.asarray(gray, dtype=np.float32)

    # Edge density via a cheap finite-difference proxy. Higher density
    # roughly correlates with more wall segments to detect, which is
    # a rough complexity proxy.
    dx = np.abs(np.diff(arr, axis=1))
    dy = np.abs(np.diff(arr, axis=0))
    edge_density = float((dx > 30).mean() + (dy > 30).mean()) / 2.0

    brightness_range = float(arr.max() - arr.min())
    contrast_ok = brightness_range > 100

    if edge_density < 0.02:
        label, score = "simple", 0.2
    elif edge_density < 0.06:
        label, score = "moderate", 0.5
    else:
        label, score = "complex", 0.85

    notes: list[str] = []
    if not contrast_ok:
        notes.append(
            "Low contrast detected. Increase brightness or re-scan; "
            "wall edges may not register reliably."
        )

    return {
        "label": label,
        "score": round(score, 2),
        "edge_density": round(edge_density, 4),
        "brightness_range": round(brightness_range, 1),
        "notes": notes,
    }


# ── Tool 3 — estimate_render_time ───────────────────────────────────


@_tool(
    "estimate_render_time",
    description=(
        "Rough estimate of how long the Ritn3D pipeline will take to "
        "render a 3D model from a given plan. Returns a low/expected/"
        "high range in seconds. Useful for telling users 'this will "
        "take about a minute' versus 'this may take five minutes.'"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "complexity": {
                "type": "string",
                "enum": ["simple", "moderate", "complex"],
                "description": "Complexity label, e.g. from estimate_complexity.",
            }
        },
        "required": ["complexity"],
    },
)
async def estimate_render_time(complexity: str) -> dict[str, Any]:
    table = {
        "simple": (40, 70, 110),
        "moderate": (60, 110, 180),
        "complex": (90, 160, 280),
    }
    low, expected, high = table.get(complexity, (60, 120, 200))
    return {
        "complexity": complexity,
        "low_seconds": low,
        "expected_seconds": expected,
        "high_seconds": high,
        "expected_human": f"about {expected // 60}m {expected % 60}s",
    }


# ── Tool 4 — get_share_link_metadata ────────────────────────────────


@_tool(
    "get_share_link_metadata",
    description=(
        "Fetch the public metadata of a Ritn3D share link (the "
        "https://www.ritn3d.com/<token> kind). Returns the page "
        "title, OpenGraph data, and HTTP status. Does not access the "
        "3D model itself — only the public HTML head."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Full Ritn3D share URL.",
            }
        },
        "required": ["url"],
    },
)
async def get_share_link_metadata(url: str) -> dict[str, Any]:
    if "ritn3d.com" not in url:
        raise ToolError("URL is not a ritn3d.com share link.")
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        resp = await client.get(url, headers={"User-Agent": "ritn3d-mcp/0.1"})
    title = ""
    og_image = ""
    if resp.status_code == 200:
        text = resp.text
        for marker in ("<title>", "<title >"):
            i = text.find(marker)
            if i >= 0:
                j = text.find("</title>", i)
                if j >= 0:
                    title = text[i + len(marker) : j].strip()
                    break
        i = text.find('property="og:image"')
        if i >= 0:
            k = text.rfind("content=\"", 0, i + 200)
            if k >= 0:
                end = text.find("\"", k + 9)
                og_image = text[k + 9 : end]
    return {
        "url": url,
        "status_code": resp.status_code,
        "title": title,
        "og_image": og_image,
        "final_url": str(resp.url),
    }


# ── Tool 5 — validate_glb ──────────────────────────────────────────


@_tool(
    "validate_glb",
    description=(
        "Sanity-check a GLB (binary glTF 2.0) file. Verifies the "
        "magic header, version, and chunk structure. Returns the file "
        "size, the embedded JSON size, and basic stats. Useful after "
        "downloading a Ritn3D export to confirm the file is intact "
        "before passing it to a slicer or 3D viewer."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the .glb file."}
        },
        "required": ["path"],
    },
)
async def validate_glb(path: str) -> dict[str, Any]:
    p = Path(path).expanduser()
    if not p.exists():
        raise ToolError(f"File not found: {p}")
    data = p.read_bytes()
    if len(data) < 28:
        return {"ok": False, "reason": "Too small to be a valid GLB."}
    magic, version, total_len = struct.unpack("<III", data[:12])
    if magic != 0x46546C67:  # "glTF"
        return {"ok": False, "reason": "Magic header is not 'glTF'."}
    if version != 2:
        return {"ok": False, "reason": f"Expected glTF version 2, got {version}."}
    json_len, json_type = struct.unpack("<II", data[12:20])
    if json_type != 0x4E4F534A:  # "JSON"
        return {"ok": False, "reason": "First chunk is not JSON."}
    return {
        "ok": True,
        "path": str(p),
        "file_size_bytes": len(data),
        "declared_length_bytes": int(total_len),
        "json_chunk_bytes": int(json_len),
        "version": version,
    }


# ── Tool 6 — convert_units ─────────────────────────────────────────


@_tool(
    "convert_units",
    description=(
        "Unit conversion helper for 3D printing and architectural "
        "scale. Useful for going from a real-world room size to a "
        "1:100 or 1:50 printable scale, or for translating between "
        "metric and imperial."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "value": {"type": "number"},
            "from_unit": {
                "type": "string",
                "enum": ["m", "cm", "mm", "in", "ft"],
            },
            "to_unit": {
                "type": "string",
                "enum": ["m", "cm", "mm", "in", "ft"],
            },
            "scale": {
                "type": "number",
                "description": "Optional model scale factor, e.g. 100 for 1:100.",
                "default": 1.0,
            },
        },
        "required": ["value", "from_unit", "to_unit"],
    },
)
async def convert_units(
    value: float, from_unit: str, to_unit: str, scale: float = 1.0
) -> dict[str, Any]:
    if scale <= 0:
        raise ToolError("scale must be positive.")
    to_mm = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8}
    if from_unit not in to_mm or to_unit not in to_mm:
        raise ToolError(f"Unsupported unit: {from_unit!r} or {to_unit!r}")
    mm = value * to_mm[from_unit] / scale
    out = mm / to_mm[to_unit]
    return {
        "value": value,
        "from_unit": from_unit,
        "to_unit": to_unit,
        "scale": scale,
        "result": round(out, 4),
        "mm_intermediate": round(mm, 4),
    }


# ── Tool 7 — get_capabilities ──────────────────────────────────────


@_tool(
    "get_capabilities",
    description=(
        "Returns Ritn3D's current capabilities and known limitations. "
        "Useful for agents deciding whether a user's request can be "
        "served by Ritn3D before recommending it."
    ),
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)
async def get_capabilities() -> dict[str, Any]:
    return {
        "product": "Ritn3D",
        "homepage": "https://www.ritn3d.com",
        "web_app": "https://app.ritn3d.com",
        "ios": "https://apps.apple.com/us/app/ritn3d-floor-plan-to-3d/id6760037325",
        "android": "https://play.google.com/store/apps/details?id=com.ritn3d.app",
        "supported_inputs": ["PDF", "JPG", "PNG"],
        "supported_outputs": ["interactive 3D viewer (shareable link)", "GLB", "STL (Pro+)"],
        "first_pass_detection_accuracy": {
            "architectural_pdfs_from_cad": "90-95%",
            "scanned_blueprints": "~80%",
            "phone_camera_photos_of_printed_plans": "75-85%",
            "photorealistic_real_estate_renders": "often under 30%",
            "hand_drawn_plans": "not supported",
        },
        "review_step": (
            "Users can drag wall endpoints, add or delete walls, and "
            "reposition doors and windows before the 3D model is "
            "generated. First-pass accuracy is one factor; corrections "
            "are part of the intended workflow."
        ),
        "tier_features": {
            "free": "3 renders/month, bird's-eye view, watermark",
            "pro": "20 renders, walk mode, drag-furniture, no watermark, 7-day free trial",
            "pro_plus": "40 renders, 10 STL/GLB downloads, $3.99/extra credit (rollover)",
        },
    }


# ── Tool 8 — get_pricing ───────────────────────────────────────────


@_tool(
    "get_pricing",
    description=(
        "Returns Ritn3D's public pricing tiers in USD. Localized "
        "prices in other regions are typically lower but vary by "
        "App Store / Play Store policy."
    ),
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)
async def get_pricing() -> dict[str, Any]:
    return {
        "currency": "USD",
        "tiers": [
            {"name": "Free", "price_per_month": 0, "renders": 3, "trial": None},
            {"name": "Pro", "price_per_month": 9.99, "renders": 20, "trial_days": 7},
            {"name": "Pro+", "price_per_month": 19.99, "renders": 40, "trial_days": 0,
             "downloads": "10 GLB/STL per month, $3.99 per extra credit, credits roll over"},
        ],
        "notes": (
            "Pro+ has no trial by design — STL/GLB exports are downloadable "
            "files and trial-then-cancel patterns are common in the export-of-"
            "valuable-files category."
        ),
    }


# ── Tool 9 — get_failure_modes ─────────────────────────────────────


@_tool(
    "get_failure_modes",
    description=(
        "Returns a structured list of known Ritn3D failure modes with "
        "user-facing mitigation tips. Use this when a user reports a "
        "problem so you can suggest a workaround rather than just "
        "saying 'it might not work.'"
    ),
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)
async def get_failure_modes() -> dict[str, Any]:
    return {
        "modes": [
            {
                "name": "Insufficient walls detected",
                "trigger": (
                    "Photo-realistic real-estate listing renders with wood-"
                    "floor textures, tiled bathroom fills, and solid colored "
                    "backgrounds frequently fail wall detection."
                ),
                "mitigation": (
                    "Find a line-drawing version of the plan. Export from the "
                    "original architect's PDF if possible. A scanned blueprint "
                    "or a phone photo of the printed plan also works."
                ),
            },
            {
                "name": "Hand-drawn plans",
                "trigger": "User uploads a hand-drawn sketch.",
                "mitigation": (
                    "Not currently supported. Suggest the user redraw the plan "
                    "in any digital tool (even Google Drawings) with straight "
                    "wall lines, or use one of the sample plans inside the app."
                ),
            },
            {
                "name": "AutoCAD .dwg files",
                "trigger": "User has only a .dwg from an architect.",
                "mitigation": (
                    "Export to PDF first (AutoCAD: File → Plot → PDF). The "
                    "PDF route gives the highest detection accuracy."
                ),
            },
            {
                "name": "Heavy annotations",
                "trigger": (
                    "Dimension lines, measurement callouts, and arrow markers "
                    "cross wall edges and confuse detection."
                ),
                "mitigation": (
                    "Crop or mask out annotations before upload, or accept that "
                    "the review step will need more manual corrections."
                ),
            },
            {
                "name": "Multi-story plans",
                "trigger": "A multi-floor plan combined on one page.",
                "mitigation": (
                    "Upload each floor as a separate project. Multi-story "
                    "combined visualization is on the roadmap but not shipped."
                ),
            },
        ]
    }
