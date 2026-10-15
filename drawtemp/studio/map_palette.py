"""Stable R5.5 palette catalog: canonical Content brush IDs, not asset aliases."""
from __future__ import annotations
from dataclasses import dataclass

from sporebound.terrain_watercolor import MATERIALS
from sporebound.terrain_schema import SURFACES, FEATURES

MIME_BRUSH = "application/x-drawtemp-map-brush"
DECOR = (
    ("tree", "Arbre"),
    ("bush", "Buisson"),
    ("boulder", "Rocher"),
    ("reeds", "Roseaux"),
    ("ruin", "Ruines"),
    ("crate", "Caisse"),
    ("lantern", "Lanterne"),
    ("stairs", "Escaliers"),
    ("stone_wall", "Mur de pierre"),
    ("arch", "Arche"),
    ("fence", "Clôture"),
    ("pillar", "Pilier"),
)
TERRAIN_NAMES = {
    "grass": "Herbe", "dirt": "Terre", "stone": "Pierre",
    "cobble": "Pavés", "sand": "Sable", "rock": "Roche",
    "water": "Eau", "bridge": "Pont",
}


@dataclass(frozen=True)
class PaletteCard:
    id: str
    label: str
    family: str
    token: str
    atlas_index: int | None


def cards():
    return tuple(
        [PaletteCard("surface:" + material, TERRAIN_NAMES[material], "Terrain",
                     material, MATERIALS.index(material)*2)
         for material in MATERIALS if material in SURFACES] +
        [PaletteCard("feature:" + feature, label, "Décors", feature, None)
         for feature, label in DECOR if feature in FEATURES]
    )


CATALOG = cards()
IDS = frozenset(card.id for card in CATALOG)


def require_brush(brush):
    if not isinstance(brush, str) or brush not in IDS:
        raise ValueError("Unsupported map palette brush")
    return brush


def find_cards(text="", family="Tous"):
    if family not in ("Tous", "Terrain", "Décors"):
        raise ValueError("Unknown map palette family")
    if not isinstance(text, str):
        raise ValueError("Palette search must be text")
    import unicodedata
    def fold(value):
        normalized = unicodedata.normalize("NFD", value.casefold())
        return "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    query = fold(text).strip()
    return tuple(card for card in CATALOG
                 if (family == "Tous" or card.family == family)
                 and (query in fold(card.label) or query in fold(card.token)))
