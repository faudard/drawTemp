"""Player-only presentation policies shared by the Tk client and headless tests.

The tactical model, combat forecasts, saves and RNG remain engine-owned.
Nothing in this module imports Tkinter or modifies a Battle.
"""
from __future__ import annotations

from dataclasses import dataclass

from .presentation import Camera


ZOOM_PRESETS = (24, 54, 96)
# Canvas-scoped shortcuts: comboboxes, text inputs and dialogs keep native keys.
KEY_CHOICES = (
    "<Return>", "<space>", "<Escape>", "<plus>", "<minus>",
    "<Up>", "<Down>", "<Left>", "<Right>",
    "<Control-Up>", "<Control-Down>", "<Control-Left>", "<Control-Right>",
    "<Key-1>", "<Key-2>", "<Key-3>", "<F1>", "<F2>",
    "<F4>", "<F6>", "<F7>", "<F8>", "<F10>",
)
DEFAULT_KEYS = {
    "execute": "<Return>", "end": "<space>", "cancel": "<Escape>",
    "zoom_in": "<plus>", "zoom_out": "<minus>",
    "north": "<Up>", "south": "<Down>",
    "west": "<Left>", "east": "<Right>",
    "pan_north": "<Control-Up>", "pan_south": "<Control-Down>",
    "pan_west": "<Control-Left>", "pan_east": "<Control-Right>",
    "zoom_24": "<Key-1>", "zoom_54": "<Key-2>", "zoom_96": "<Key-3>",
}


class KeyBindings:
    """User-remappable, non-overlapping shortcuts for the tactical Canvas."""

    def __init__(self, assignments=None):
        self._keys = dict(DEFAULT_KEYS)
        if assignments:
            self.replace(assignments)

    def replace(self, assignments):
        candidate = dict(self._keys)
        for action, sequence in assignments.items():
            if action not in candidate:
                raise ValueError("Unknown Player action: " + str(action))
            if sequence not in KEY_CHOICES:
                raise ValueError("Unsupported Player shortcut: " + str(sequence))
            candidate[action] = sequence
        if len(set(candidate.values())) != len(candidate):
            raise ValueError("Each Player action needs a different shortcut")
        self._keys = candidate

    def items(self):
        return tuple(self._keys.items())

    def get(self, action):
        return self._keys[action]


class PresentationState:
    """Invalidate late animation/cinematic callbacks after any screen change."""

    def __init__(self):
        self.screen = "title"
        self.overlay = None
        self.revision = 0

    def transition(self, screen):
        self.screen = screen
        self.overlay = None
        self.revision += 1
        return self.revision

    def begin_overlay(self, name):
        if self.overlay is not None:
            raise ValueError("An overlay is already active")
        self.overlay = name
        self.revision += 1
        return self.revision

    def close_overlay(self):
        self.overlay = None
        self.revision += 1
        return self.revision

    def current(self, revision):
        return revision == self.revision


def zoom_to(camera: Camera, cell_size: int, anchor=(0, 0)):
    """Anchor an exact 24/54/96px 2D zoom without moving the target cell."""
    if cell_size not in ZOOM_PRESETS:
        raise ValueError("Unknown Player zoom preset")
    x, y = anchor
    world_x = (x - camera.offset_x) / camera.cell_size
    world_y = (y - camera.offset_y) / camera.cell_size
    return Camera(cell_size, x - world_x * cell_size,
                  y - world_y * cell_size)


def clamp_selection(cell, width, height):
    """Keep keyboard selection inside an authored board, including tiny maps."""
    if width <= 0 or height <= 0:
        raise ValueError("Board must have positive dimensions")
    return (min(width - 1, max(0, int(cell[0]))),
            min(height - 1, max(0, int(cell[1]))))


@dataclass(frozen=True)
class CombatHUD:
    headline: str
    objective: str
    selection_summary: str
    roster: tuple[str, ...]
    timeline: tuple[str, ...]
    forecasts: tuple[str, ...]
    warnings: tuple[str, ...]


def combat_hud(frame, objective="", cell=None):
    """Render only known facts, not hypothetical AI outcomes or LOS guesses."""
    if frame is None:
        raise ValueError("A combat frame is required")
    cell = tuple(cell) if cell is not None else frame.selected
    if cell is not None and not (0 <= cell[0] < frame.width and
                                 0 <= cell[1] < frame.height):
        raise ValueError("Selection outside battle")
    headline = ("Combat terminé : " + frame.result if frame.result else
                "Déploiement" if frame.deploying else
                "Tour actif : " + str(frame.active_id or "ordonnancement"))
    roster = tuple(
        ("► " if actor.active else "  ") + actor.name +
        " [" + actor.team + "] PV " + str(actor.hp) + "/" + str(actor.max_hp) +
        " · MP " + str(actor.mp) + "/" + str(actor.max_mp) +
        (" · KO" if not actor.alive else "")
        for actor in frame.actors
    )
    timeline = tuple(
        str(row["unit"]) + " : " +
        ("actif" if row["active"] else "bloqué" if row["eta_ticks"] is None else
         "CT t+" + str(row["eta_ticks"]) + " (estimation)")
        for row in frame.timeline
    )
    forecasts = tuple(
        str(row.get("kind", "action")) + " : " + str(row.get("amount", "?")) +
        (" (chance " + str(round(row["chance"] * 100)) + "%)"
         if isinstance(row.get("chance"), (int, float)) else "")
        for row in frame.forecast
    )
    warnings = []
    if cell is None:
        selection = "Aucune case sélectionnée"
    else:
        units = [
            actor for actor in frame.actors if actor.alive and
            actor.pos[0] <= cell[0] < actor.pos[0] + actor.footprint[0] and
            actor.pos[1] <= cell[1] < actor.pos[1] + actor.footprint[1]
        ]
        selection = "Case " + str(cell)
        if units:
            selection += " · " + ", ".join(
                actor.name + " PV " + str(actor.hp) + "/" + str(actor.max_hp)
                for actor in units)
        if cell in frame.reachable:
            selection += " · déplacement accessible (coût non prédit)"
        dangers = [row for row in frame.danger if tuple(row["cell"]) == cell]
        certainty = {
            "hazard": "terrain dangereux (certain)",
            "cast": "sort programmé",
            "prepared": "réaction armée",
            "charge": "charge possible, non garantie",
        }
        warnings.extend(certainty.get(row["kind"], row["kind"])
                        for row in dangers)
        if warnings:
            selection += " · " + "; ".join(dict.fromkeys(warnings))
    return CombatHUD(headline, str(objective), selection, roster, timeline,
                     forecasts, tuple(dict.fromkeys(warnings)))
