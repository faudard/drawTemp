"""R22.2A deterministic, non-destructive terrain generation for the R5 map.

No second map format, RNG side effects or separate history. A preview captures
the canonical AuthoringSession lease; commit applies exactly that validated plan.
Existing authored tiles and gameplay-linked cells are preserved by design.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256

from drawtemp.core import RuleError
from drawtemp.sdk.authoring import AuthoringError
from drawtemp.sdk.simulation import thaw
from sporebound.map_authoring import selected_cells
from .map_selection import _occupied, _reserved, MAX_SELECTION
from .map_authoring import _mission


# Surface names come from the existing v1 terrain schema, not a custom palette.
BIOMES = {
    "Prairie": (("grass", 65), ("dirt", 20), ("sand", 10), ("stone", 5)),
    "Forêt": (("grass", 65), ("dirt", 30), ("stone", 5)),
    "Roche": (("stone", 65), ("cobble", 25), ("grass", 10)),
    "Marais": (("grass", 45), ("water", 30), ("dirt", 25)),
}


def _hash(seed, x, y, channel):
    # Stable across machines / Python versions; NEVER use process-randomized hash.
    raw = f"r22.2:{seed}:{x}:{y}:{channel}".encode("ascii")
    return int.from_bytes(sha256(raw).digest()[:8], "big")


def _surface(seed, biome, x, y):
    # Coarse cells form visually coherent four-tile terrain patches; a small,
    # coordinate-stable jitter avoids needing mutable/global RNG state.
    coarse = _hash(seed, x // 4, y // 4, "region") % 100
    jitter = _hash(seed, x, y, "detail") % 9
    roll = (coarse * 9 + jitter * 10) // 10
    accumulated = 0
    for surface, weight in BIOMES[biome]:
        accumulated += weight
        if roll < accumulated:
            return surface
    return BIOMES[biome][-1][0]


@dataclass(frozen=True)
class GenerationPreview:
    revision: int
    mission_id: str
    seed: int
    biome: str
    coverage: int
    cells: tuple[tuple[int, int, str], ...]
    protected_count: int
    plan: object


def prepare_generation(studio, *, seed, biome, coverage=75, cells=None):
    """Dry-run selected or entire map; no file, authoring or global RNG writes."""
    if type(seed) is not int or not 0 <= seed <= 2_147_483_647:
        raise RuleError("Seed must be an integer from 0 to 2147483647")
    if biome not in BIOMES:
        raise RuleError("Unknown terrain biome")
    if type(coverage) is not int or not 1 <= coverage <= 100:
        raise RuleError("Coverage must be an integer from 1 to 100")

    snapshot = studio.snapshot()
    mid = studio.mission_id
    mission = _mission(snapshot["content"], mid)
    width, height = mission["board"]["width"], mission["board"]["height"]
    if cells is None:
        if width * height > MAX_SELECTION:
            raise RuleError("Map exceeds 4096 cells; select a smaller region")
        chosen = tuple((x, y) for y in range(height) for x in range(width))
    else:
        chosen = selected_cells(snapshot["content"], mid, list(cells))
        if not chosen or len(chosen) > MAX_SELECTION:
            raise RuleError("Select between 1 and 4096 map cells")

    occupied_units, occupied_objects = _occupied(mission)
    protected = set(_reserved(mission))
    for footprint in (*occupied_units.values(), *occupied_objects.values()):
        protected.update(footprint)
    protected.update(tuple(cell) for cell in mission.get("goal", ()))
    authored = {tuple(tile["pos"]) for tile in mission["board"]["tiles"]}
    forbidden = authored | protected

    # Coverage and surface rolls depend only on global tile coordinates and
    # seed. Selecting a subregion cannot change results at shared coordinates.
    result = tuple(
        (x, y, _surface(seed, biome, x, y))
        for x, y in sorted(chosen, key=lambda c: (c[1], c[0]))
        if (x, y) not in forbidden and _hash(seed, x, y, "coverage") % 100 < coverage
    )
    if not result:
        raise RuleError("No available empty cells to generate; change selection or seed")
    def apply(content, project):
        before = deepcopy(content)
        target = _mission(content, mid)
        existing = {tuple(tile["pos"]): tile for tile in target["board"]["tiles"]}
        for x, y, surface in result:
            tile = {"pos": [x, y], "surface": surface}
            if surface == "water":
                tile["blocked"] = True
            existing[x, y] = tile
        target["board"]["tiles"] = [
            existing[cell] for cell in sorted(existing, key=lambda c: (c[1], c[0]))
        ]
        studio.layers.assert_editable(before, content)
        return content, project

    plan = studio.authoring.preview_pair(
        apply, kind="r22.2-terrain-generation", mission_id=mid
    )
    return GenerationPreview(
        snapshot["revision"], mid, seed, biome, coverage, result,
        sum(cell in forbidden for cell in chosen), plan
    )


def commit_generation(studio, preview):
    """Respect revision + mission lease AND locks changed since preview."""
    if not isinstance(preview, GenerationPreview):
        raise RuleError("Expected a terrain generation preview")
    if (preview.mission_id != studio.mission_id or
            preview.revision != studio.authoring.revision):
        raise AuthoringError("stale_revision", "terrain-generation",
                             "Map changed; regenerate the preview")
    # Layer locks are UI state, not AuthoringSession history: check again.
    studio.layers.assert_editable(
        studio.snapshot()["content"], thaw(preview.plan.content)
    )
    return studio.authoring.apply(preview.plan)
