"""R50.B creator catalog: real R28/R15 authoring, explicit genre blockers.

This module reuses the canonical Content/GameProject, AuthoringSession and
GameSession. It deliberately does not turn a tactical game into a fake action,
RPG_TURN, platformer, roguelite or hybrid Player merely by labelling it.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.r28e_minigames import (
    MiniGameError, audit_minigame, create_minigame,
)


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class Starter:
    key: str
    label: str
    genre: str
    minigame: str | None
    limitation: str


STARTERS = (
    Starter("srpg", "Le duel du village", "srpg", "duel_tactique",
            "Test headless CT seulement; Player natif et export 9.0 non certifiés."),
    Starter("action_adventure", "La vallée des lanternes", "action_adventure",
            None, "Studio → Player action temps réel non prouvé de bout en bout."),
    Starter("classic_rpg", "Le relais des trois compagnons", "classic_rpg",
            None, "RPG_TURN, groupe et Player menus non intégrés sur cette base."),
    Starter("metroidvania", "La citadelle suspendue", "metroidvania",
            None, "Parcours Studio/platformer et capacités de progression non certifiés."),
    Starter("roguelite", "Les salles mouvantes", "roguelite",
            None, "Génération, méta-progression, replay et Player non certifiés."),
    Starter("narrative_hybrid", "Le conseil des gardes", "narrative_hybrid",
            None, "Transition récit→action/CT→récit non certifiée."),
    Starter("narrative_prototype", "Le choix du village", "narrative",
            "choix_village", "Démonstrateur narratif à choix, PAS un hybride."),
)
_BY_KEY = {row.key: row for row in STARTERS}
REQUIRED_GENRES = (
    "srpg", "action_adventure", "classic_rpg",
    "metroidvania", "roguelite",
)


def starter(key: str) -> Starter:
    if type(key) is not str or key not in _BY_KEY:
        raise CatalogError("Unknown R50.B starter: " + repr(key))
    return _BY_KEY[key]


def catalog() -> dict:
    """Static allowlist of workflows actually connected on this master baseline."""
    return {
        "kind": "drawtemp-r50b-creator-catalog",
        "schema": 1,
        "entries": [
            {"id": item.key, "title": item.label, "genre": item.genre,
             "status": "headless-authoring" if item.minigame else "blocked",
             "can_create": item.minigame is not None,
             "limitation": item.limitation}
            for item in STARTERS
        ],
        "required_genres": list(REQUIRED_GENRES),
        "missing_creation_genres": [
            item.key for item in STARTERS
            if item.key in REQUIRED_GENRES and item.minigame is None
        ],
        "real_qt_onscreen_verified": False,
        "native_player_verified": False,
        "export_pc_verified": False,
        "release_9_0_ready": False,
    }


def preview_starter(key: str, destination: str | Path) -> dict:
    """Read-only diagnostic; never reinterpret an unsupported mode as SRPG."""
    entry = starter(key)
    errors = []
    if (not isinstance(destination, (str, Path)) or
            not str(destination).strip()):
        target = None
        errors.append("A new project destination is required")
    else:
        target = Path(destination).expanduser().absolute()
        if target.exists() or target.is_symlink():
            errors.append("Destination already exists")
        if not target.parent.is_dir():
            errors.append("Destination parent directory must exist")
        if target.parent == target:
            errors.append("Destination must be a new subdirectory")
    if entry.minigame is None:
        errors.append(entry.limitation)
    return {
        "kind": "drawtemp-r50b-starter-preview",
        "template": entry.key,
        "destination": str(target) if target is not None else "",
        "can_create": not errors,
        "errors": errors,
        "will_write": ["game.json", "game.game.json"] if not errors else [],
        "r50_release_certified": False,
    }


def _authoring_rehearsal(content_path: Path, minigame: str) -> dict:
    """Actual R1 preview/apply/undo/redo/save/reopen and R28 GameSession replay.

    Only call on a freshly staged starter. No changes to an existing project.
    """
    session = AuthoringSession.open(content_path)
    initial = session.snapshot().to_dict()
    before_subtitle = initial["project"]["subtitle"]
    suffix = " — Atelier R50.B"
    def edit(project):
        project["subtitle"] = before_subtitle + suffix
        return project
    plan = session.preview_project(edit, kind="r50b.authoring-rehearsal")
    session.apply(plan)
    changed = session.snapshot().to_dict()
    if changed["project"]["subtitle"] != before_subtitle + suffix:
        raise CatalogError("Authoring edit was not applied")
    session.undo()
    if session.snapshot().to_dict()["project"] != initial["project"]:
        raise CatalogError("Undo did not restore the original project")
    session.redo()
    if session.snapshot().to_dict()["project"] != changed["project"]:
        raise CatalogError("Redo did not restore the authored project")
    session.save()
    reopened = AuthoringSession.open(content_path)
    saved = reopened.snapshot().to_dict()
    if saved["project"] != changed["project"] or saved["content"] != changed["content"]:
        raise CatalogError("Canonical save/reopen differs from authored state")
    if reopened.snapshot().dirty:
        raise CatalogError("Saved document still marked dirty")
    audit = audit_minigame(content_path, minigame)
    if not (audit["preflight_passed"] and audit["game_session_roundtrip"]
            and audit["author_documents_unchanged"]):
        raise CatalogError("GameSession replay or preflight did not pass")
    return {
        "transactional_edit": True,
        "undo_redo": True,
        "saved_and_reopened": True,
        "content_project_preflight": True,
        "gamesession_checkpoint_roundtrip": True,
        "checkpoint_digest": audit["checkpoint_digest"],
        "gameplay": audit["gameplay"],
        "native_player_tested": False,
        "qt_onscreen_tested": False,
        "standalone_export_tested": False,
    }


def create_starter(key: str, destination: str | Path) -> dict:
    """Build in isolation; publish only after a real headless author/Player audit.

    An unsupported runtime fails without creating anything at the destination.
    """
    report = preview_starter(key, destination)
    if not report["can_create"]:
        raise CatalogError("; ".join(report["errors"]))
    entry = starter(key)
    target = Path(report["destination"])
    try:
        with TemporaryDirectory(prefix=".drawtemp-r50b-", dir=target.parent) as temp:
            staged = Path(temp) / "starter"
            create_minigame(entry.minigame, staged)
            outcome = _authoring_rehearsal(staged / "game.json", entry.minigame)
            if target.exists() or target.is_symlink():
                raise CatalogError("Destination claimed during staging")
            os.rename(staged, target)
    except (MiniGameError, OSError, ValueError) as exc:
        raise CatalogError("R50.B creator workflow rejected: " + str(exc)) from exc
    return {
        "kind": "drawtemp-r50b-authoring-journey",
        "schema": 1, "starter": entry.key, "genre": entry.genre,
        "content_path": str(target / "game.json"),
        "proof": outcome, "status": "headless-pass",
        "release_9_0_ready": False,
        "blockers": ["Qt onscreen/physical Player not exercised",
                     "Clean-machine native export not exercised",
                     "R40/R41–R49 acceptance and R50.C certification missing"],
    }
