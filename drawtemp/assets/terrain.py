"""R4 terrain/material presentation adapter over the already canonical map code.

Materials and seeded joins are calculated in world coordinates. No new board
schema, gameplay RNG, second procedural algorithm or Qt/Tk imports are added.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sporebound.terrain_schema import SURFACES
from sporebound.terrain_autoblend import (
    blend_edges, surface_at, terrain_variant, REGION_STYLES,
)
from sporebound.environment_atlas import (
    FRAME_SIZE, FRAME_COUNT, KINDS as ENVIRONMENT_KINDS,
    PIVOTS, environment_strip_png, export_atlases,
)


@dataclass(frozen=True)
class TerrainMaterial:
    name: str
    variant: int
    edges: tuple


def material_at(x: int, y: int, *, seed: int = 0, style: str = "prairie",
                variants: int = 2) -> TerrainMaterial:
    """Deterministic default material with a repeatable texture variation."""
    material = surface_at(x, y, seed=seed, style=style)
    if material not in SURFACES:
        raise ValueError("Unknown terrain material")
    return TerrainMaterial(material, terrain_variant((x, y), variants, seed=seed), ())


def map_material(board, x: int, y: int, *, seed: int = 0,
                 variants: int = 2) -> TerrainMaterial:
    """Read an authored board, including neighbour-aware AutoBlend edges."""
    if not board.contains((x, y)):
        raise ValueError("Cell is outside map bounds")
    material = board.tile((x, y)).surface
    if material not in SURFACES:
        raise ValueError("Unknown terrain material")
    edges = tuple((edge.bit, edge.incoming, edge.pattern)
                  for edge in blend_edges(board, (x, y)))
    return TerrainMaterial(material, terrain_variant((x, y), variants, seed=seed),
                           edges)


def animated_environment_assets():
    """Metadata for identical generated strips in Studio/Player."""
    return tuple({
        "id": "environment." + kind,
        "kind": kind,
        "frame_count": FRAME_COUNT,
        "frame_size": (FRAME_SIZE, FRAME_SIZE),
        "pivot": PIVOTS[kind],
        "duration_ms": 125,
    } for kind in ENVIRONMENT_KINDS)


def export_animated_environment(folder: Path):
    """Reuse existing deterministic RGBA art generator (no static placeholders)."""
    return export_atlases(folder)


def environment_preview(kind: str) -> bytes:
    """Get an actual 8-frame strip for a Qt image provider or an import tool."""
    if kind not in ENVIRONMENT_KINDS:
        raise ValueError("Unknown animated environment asset")
    return environment_strip_png(kind)
