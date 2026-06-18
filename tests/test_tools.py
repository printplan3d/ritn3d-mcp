"""Smoke tests — verify every tool's contract without hitting the network."""

import io
from pathlib import Path

import pytest
from PIL import Image

from ritn3d_mcp.tools import (
    TOOL_REGISTRY,
    convert_units,
    estimate_complexity,
    estimate_render_time,
    get_capabilities,
    get_failure_modes,
    get_pricing,
    validate_floor_plan_image,
    validate_glb,
)


def _make_image(tmp_path: Path, w: int = 1024, h: int = 1024) -> Path:
    img = Image.new("RGB", (w, h), color=(255, 255, 255))
    p = tmp_path / "plan.jpg"
    img.save(p, format="JPEG")
    return p


def _make_glb(tmp_path: Path) -> Path:
    import struct
    json_bytes = b'{"asset":{"version":"2.0"}}'
    pad = b" " * ((4 - len(json_bytes) % 4) % 4)
    json_chunk = json_bytes + pad
    body = (
        struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(json_chunk))
        + struct.pack("<II", len(json_chunk), 0x4E4F534A)
        + json_chunk
    )
    p = tmp_path / "model.glb"
    p.write_bytes(body)
    return p


def test_registry_has_expected_tools():
    expected = {
        "validate_floor_plan_image",
        "estimate_complexity",
        "estimate_render_time",
        "get_share_link_metadata",
        "validate_glb",
        "convert_units",
        "get_capabilities",
        "get_pricing",
        "get_failure_modes",
    }
    assert expected.issubset(TOOL_REGISTRY.keys())


@pytest.mark.asyncio
async def test_validate_floor_plan_image_ok(tmp_path):
    p = _make_image(tmp_path)
    out = await validate_floor_plan_image(str(p))
    assert out["ok"] is True
    assert out["width"] == 1024
    assert out["format"] == "JPEG"


@pytest.mark.asyncio
async def test_validate_floor_plan_image_small_warns(tmp_path):
    p = _make_image(tmp_path, 400, 400)
    out = await validate_floor_plan_image(str(p))
    assert out["ok"] is False
    assert any("small" in w.lower() for w in out["warnings"])


@pytest.mark.asyncio
async def test_estimate_complexity(tmp_path):
    p = _make_image(tmp_path)
    out = await estimate_complexity(str(p))
    assert out["label"] in {"simple", "moderate", "complex"}
    assert 0 <= out["score"] <= 1


@pytest.mark.asyncio
async def test_estimate_render_time_keys():
    out = await estimate_render_time("moderate")
    assert out["expected_seconds"] > 0
    assert "expected_human" in out


@pytest.mark.asyncio
async def test_convert_units_m_to_mm():
    out = await convert_units(value=2.7, from_unit="m", to_unit="mm")
    assert abs(out["result"] - 2700.0) < 0.01


@pytest.mark.asyncio
async def test_convert_units_scale():
    # 2.7 m at 1:100 scale should be 27 mm
    out = await convert_units(value=2.7, from_unit="m", to_unit="mm", scale=100)
    assert abs(out["result"] - 27.0) < 0.01


@pytest.mark.asyncio
async def test_validate_glb(tmp_path):
    p = _make_glb(tmp_path)
    out = await validate_glb(str(p))
    assert out["ok"] is True
    assert out["version"] == 2


@pytest.mark.asyncio
async def test_get_capabilities_has_known_keys():
    out = await get_capabilities()
    assert out["product"] == "Ritn3D"
    assert "first_pass_detection_accuracy" in out


@pytest.mark.asyncio
async def test_get_pricing_tiers():
    out = await get_pricing()
    assert {t["name"] for t in out["tiers"]} == {"Free", "Pro", "Pro+"}


@pytest.mark.asyncio
async def test_get_failure_modes_nonempty():
    out = await get_failure_modes()
    assert len(out["modes"]) >= 5
