"""R28.A: safe multi-genre entry point over the canonical R15 creator.

The preview is deliberately declarative: it is NOT a new GameProject schema.
Unsupported runtime modes must never be silently saved as a tactical game.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from drawtemp.export.templates import create_template


@dataclass(frozen=True)
class GenrePreset:
    key: str
    label: str
    description: str
    template: str | None
    movement: str
    combat: str
    camera: str
    limitation: str = ""


GENRES = (
    GenrePreset("srpg", "SRPG tactique",
                "Missions tactiques sur grille avec CT (format historique).",
                "tactical", "GRID_CT", "TACTICAL_CT", "ISOMETRIC"),
    GenrePreset("action_adventure", "Action-aventure",
                "Exploration libre, collisions et combats temps reel.",
                None, "FREE_REALTIME", "ACTION_REALTIME", "TOP_DOWN",
                "R25/R26 : moteur et schema de profil action non integres."),
    GenrePreset("classic_rpg", "RPG classique",
                "Exploration et rencontres avec combat par menus.",
                None, "FREE_REALTIME", "RPG_TURN", "TOP_DOWN",
                "R28.9 : combat RPG par tours et transition non integres."),
    GenrePreset("narrative", "Aventure narrative",
                "Modele narratif R15 compatible avec le moteur tactique v1.",
                "narrative", "GRID_CT", "TACTICAL_CT", "ISOMETRIC"),
    GenrePreset("hybrid", "Jeu hybride",
                "Exploration libre puis combat CT avec retour.",
                None, "MIXED", "ACTION_REALTIME + TACTICAL_CT", "MIXED",
                "R25 : transitions, profils de scenes et save/replay mixtes absents."),
)
_BY_KEY = {item.key: item for item in GENRES}


def genre_preset(key: str) -> GenrePreset:
    """Reject unknown presets without falling back to the tactical template."""
    if key not in _BY_KEY:
        raise ValueError("Genre de projet inconnu : " + str(key))
    return _BY_KEY[key]


def preview_genre_project(key: str, destination: str | Path) -> dict:
    """Validate the request without writing a file or mutating a project.

    The proposed modes are UI descriptors, not persisted gameplay settings.
    """
    preset = genre_preset(key)
    errors = []
    if not isinstance(destination, (str, Path)) or not str(destination).strip():
        errors.append("Choisissez un dossier de destination.")
        path = None
    else:
        path = Path(destination).expanduser().absolute()
        if path.exists():
            errors.append("La destination existe deja : aucun ecrasement autorise.")
        elif path.parent == path:
            errors.append("La racine du disque n'est pas une destination valide.")
    if preset.template is None:
        errors.append(preset.limitation)
    return {
        "genre": preset.key,
        "label": preset.label,
        "description": preset.description,
        "destination": str(path) if path else "",
        "template": preset.template,
        "proposed_profile": {
            "movement": preset.movement, "combat": preset.combat,
            "camera": preset.camera, "persistence": "NOT_WRITTEN",
        },
        "status": "available-v1" if preset.template else "blocked-dependency",
        "errors": errors,
        "passed": not errors,
    }


def create_genre_project(key: str, destination: str | Path) -> Path:
    """Create a canonical Content/GameProject pair or fail without side effects."""
    report = preview_genre_project(key, destination)
    if not report["passed"]:
        raise ValueError("; ".join(report["errors"]))
    # R15 writes to a staging directory, validates both canonical documents
    # and atomically moves them into a new (non-existing) destination.
    return create_template(report["template"], report["destination"])
