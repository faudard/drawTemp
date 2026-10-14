"""R7.10 — Read-only Combat HUD sections, independent from Tk.

BattleFrame is the sole source for CT, combat logs, health/MP and selections.
No mission rules, gameplay actions or saved layout fields are introduced.
"""
from __future__ import annotations

from dataclasses import dataclass

from .player_ux import combat_hud


@dataclass(frozen=True)
class CombatHudSections:
    title: str
    objective: str
    phase: str
    timeline: tuple[str, ...]
    party: tuple[str, ...]
    focus: str
    journal: tuple[str, ...]
    selection: str


def combat_hud_sections(frame, objective="", *, compact=False, timeline_limit=8,
                        journal_limit=30):
    """Snapshot stable, text-accessible HUD groups from the canonical frame."""
    if frame is None:
        raise ValueError("BattleFrame required")
    if type(compact) is not bool or type(timeline_limit) is not int or timeline_limit < 1:
        raise ValueError("Invalid HUD density or timeline limit")
    if type(journal_limit) is not int or journal_limit < 0:
        raise ValueError("Invalid journal limit")
    hud = combat_hud(frame, objective=objective)
    active = next((a for a in frame.actors if a.id == frame.active_id), None)
    focus = ("Actif : " + active.name +
             " · PV " + str(active.hp) + "/" + str(active.max_hp) +
             " · MP " + str(active.mp) + "/" + str(active.max_mp)
             if active is not None else hud.headline)
    timeline = hud.timeline[:timeline_limit]
    if len(hud.timeline) > timeline_limit:
        timeline += ("+" + str(len(hud.timeline) - timeline_limit) + " activations",)
    party = tuple(row for row, actor in zip(hud.roster, frame.actors)
                  if actor.team == "player")
    if compact:
        party = party[:4]
    # Preserve textual engine evidence; never attach inferred events.
    events = frame.events[-journal_limit:] if journal_limit else ()
    journal = tuple(str(event) for event in events)
    return CombatHudSections(
        frame.mission, str(objective), hud.headline, timeline, party, focus,
        journal, hud.selection_summary)
