"""R41.B2 — encounter authoring on the canonical R1 GameProject transaction."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.classic_party import EXTENSION
from sporebound.game_modes import resolve_scene_profile
from sporebound.model import require


@dataclass(frozen=True)
class EncounterDraft:
    plan: object
    before: dict | None
    after: dict
    encounter_id: str
    revision: int


def _pair(snapshot):
    return snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot


def available_rpg_scenes(snapshot):
    project = _pair(snapshot)["project"]
    modes = project.get("game_modes") or {}
    return tuple(sorted(scene for scene in project.get("exploration", {})
                        if resolve_scene_profile(modes, scene)["combat"]
                        == "RPG_TURN"))


def available_rpg_enemies(snapshot):
    rows = {}
    for mission in _pair(snapshot)["content"]["missions"]:
        for actor in mission["units"]:
            if actor["team"] == "enemy":
                rows.setdefault(actor["id"], actor.get("name", actor["id"]))
    return tuple(sorted(rows.items()))


def encounter_definitions(snapshot):
    return deepcopy(_pair(snapshot)["project"].get("extensions", {})
                    .get(EXTENSION, {}).get("data", {}).get("encounters", {}))


def preview_encounter_edit(session: AuthoringSession, encounter_id, *,
                           scene, enemies, reward_gold, expected_revision=None):
    snapshot = session.snapshot()
    if expected_revision is not None:
        require(type(expected_revision) is int
                and expected_revision == snapshot.revision,
                "Stale R41 encounter preview")
    require(type(enemies) is list, "Encounter enemies must be a list")
    project = _pair(snapshot)["project"]
    require(EXTENSION in project.get("extensions", {}),
            "Configure Party Studio before editing encounters")
    data = {"scene": scene, "enemies": deepcopy(enemies),
            "reward_gold": reward_gold}
    old = encounter_definitions(snapshot).get(encounter_id)

    def edit(project_data):
        project_data["extensions"][EXTENSION]["data"].setdefault(
            "encounters", {})[encounter_id] = deepcopy(data)
        return project_data

    plan = session.preview_project(edit, kind="r41.encounter.configure")
    return EncounterDraft(plan, old, data, encounter_id, snapshot.revision)


def apply_encounter_edit(session: AuthoringSession, draft: EncounterDraft):
    require(isinstance(draft, EncounterDraft),
            "Missing RPG encounter preview")
    return session.apply(draft.plan)


__all__ = ["EncounterDraft", "available_rpg_scenes",
           "available_rpg_enemies", "encounter_definitions",
           "preview_encounter_edit", "apply_encounter_edit"]
