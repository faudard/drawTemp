"""R60.B1 — original hybrid production showcase on canonical R53/R55/R51.

This is an editable, headless production slice, NOT a 10.0 release gate.
All gameplay remains with GameSession; content with Content/GameProject v1.
"""
from __future__ import annotations

from drawtemp.creator_examples.r53_hybrid import build_relais_hybride_r53
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.r51_layout_authoring import LayoutAuthoring
from drawtemp.studio.system_design_authoring import (
    apply_system_design, preview_system_design,
)
from sporebound.game_project import GameProject
from sporebound.ui_layout_r51 import catalog_from_project

TITLE = "Les Sentinelles de l'Ambre"
ECONOMY_QUEST = "relight_beacon"
MERCHANT = "artisan_village"
CONTENT_REGIONS = ("village", "woods", "crypt")


def systems_document():
    """One finite, replay-verified R55 inventory; no shadow currency."""
    return {
        "version": 1,
        "resources": [
            {"id": "resin", "initial": 8, "capacity": 20},
            {"id": "lantern", "initial": 0, "capacity": 20},
        ],
        "producers": [
            {"id": "lantern_workshop", "inputs": {"resin": 2},
             "outputs": {"lantern": 1}, "interval": 2},
        ],
        "merchants": [
            {"id": MERCHANT, "resource": "lantern", "scene": "village",
             "buy_price": 5, "sell_price": 2},
        ],
        "quests": [
            {"id": ECONOMY_QUEST, "resource": "lantern", "quantity": 2,
             "flag": "beacon_supplied"},
        ],
    }


def _hud(kind, children, focus_order=()):
    return {
        "kind": kind,
        "root": {"id": "root", "type": "column", "children": children},
        "breakpoints": [
            {"min_width": 0, "columns": 1},
            {"min_width": 900, "columns": 2},
        ],
        "focus_order": list(focus_order),
    }


def ui_layouts():
    """Only typed, read-only R51 bindings and whitelisted action intents."""
    return {
        "r60_exploration": _hud("HUD_ACTION", [
            {"id": "title", "type": "text", "text": TITLE},
            {"id": "zone", "type": "text",
             "binding": {"path": "session.scene_id", "type": "str"}},
            {"id": "objective", "type": "text",
             "text": "Rallumer le phare et secourir le relais"},
        ]),
        "r60_tactical": _hud("HUD_CT", [
            {"id": "phase", "type": "text",
             "binding": {"path": "combat.phase", "type": "str"}},
            {"id": "hp", "type": "gauge",
             "binding": {"path": "combat.active_hp", "type": "int"},
             "max_binding": {"path": "combat.active_max_hp", "type": "int"}},
            {"id": "end_turn", "type": "button",
             "text": "Fin du tour", "action": "combat.end_turn"},
        ], ("end_turn",)),
        "r60_inventory": _hud("INVENTORY", [
            {"id": "inventory_title", "type": "text",
             "text": "Sac des Sentinelles"},
            {"id": "items", "type": "text",
             "binding": {"path": "inventory.item_count", "type": "int"}},
            {"id": "close", "type": "button", "text": "Fermer",
             "action": "inventory.close"},
        ], ("close",)),
    }


def author_showcase():
    """Build via the *same transactional* AuthoringSession used by Studio.

    Previews are checked and explicitly applied. No direct state edits after
    authoring, no auto-migration, no sidecars, and no second gameplay engine.
    """
    content, project = build_relais_hybride_r53()
    project.title = TITLE
    project.subtitle = (
        "Le village, les bois et la crypte : exploration, equipe, "
        "combats RPG/CT et economie d'une lanterne."
    )
    # This is a new fictional presentation over native R53 mechanics.
    for scene in project.story["scenes"]:
        if scene["id"] == "village":
            scene["title"] = "Le bourg de l'Ambre"
            scene["text"] = "Les artisans attendent que le phare soit rallume."
        elif scene["id"] == "woods":
            scene["title"] = "La foret de l'Ambre"
        elif scene["id"] == "crypt":
            scene["title"] = "Les fondations du phare"

    # R53 defaults to GRID_TURN for its classic RPG scenes. R60 adds
    # genuine fixed-step exploration without changing the native RPG combat
    # authority. The CT mission keeps its explicit srpg/GRID_CT profile.
    for scene in CONTENT_REGIONS:
        project.game_modes["scenes"][scene] = {"profile": {
            "movement": "FREE_REALTIME", "combat": "RPG_TURN",
            "camera": "TOP_DOWN", "interaction": "CONTEXTUAL", "ui": "RPG",
        }}

    editor = AuthoringSession(content, project)
    proposal = preview_system_design(
        editor, systems_document(), expected_revision=editor.revision)
    apply_system_design(editor, proposal)
    ui = LayoutAuthoring(editor)
    for layout_id, layout in ui_layouts().items():
        ui.apply(ui.preview_replace(
            layout_id, layout, expected_revision=editor.revision))
    snapshot = editor.snapshot().to_dict()
    final = GameProject.from_dict(snapshot["project"], content)
    if set(catalog_from_project(final)["layouts"]) != set(ui_layouts()):
        raise AssertionError("R60 authored HUD catalog was not persisted")
    return editor


def build_sentinelles_ambre():
    """Return a detached, validated Content + GameProject v1 pair."""
    editor = author_showcase()
    data = editor.snapshot().to_dict()
    from sporebound.model import Content
    content = Content.from_dict(data["content"])
    project = GameProject.from_dict(data["project"], content)
    return content, project


__all__ = [
    "TITLE", "ECONOMY_QUEST", "MERCHANT", "CONTENT_REGIONS",
    "systems_document", "ui_layouts", "author_showcase",
    "build_sentinelles_ambre",
]
