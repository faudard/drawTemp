"""R8.B — Qt-neutral talent trees and mission encounter authoring.

This adapter never defines a second RPG schema. Content v1 and GameProject
remain authoritative and every edit is one R1 AuthoringSession transaction.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from drawtemp.sdk.authoring import AuthoringSession
from sporebound import actor_catalog, authoring, class_ai_authoring, entity_editing
from sporebound.model import RuleError, require


@dataclass(frozen=True)
class EncounterUnit:
    id: str
    name: str
    team: str
    x: int
    y: int
    archetype: str
    weapon: str


class RulesWorkbench:
    """Talent/encounter authoring on the same revisioned document as R8.A."""

    def __init__(self, session: AuthoringSession):
        if not isinstance(session, AuthoringSession):
            raise TypeError("Expected AuthoringSession")
        self.session = session

    def documents(self):
        return self.session.snapshot().to_dict()

    def _content(self):
        return self.documents()["content"]

    def _edit(self, transform, *, mission_id=None):
        plan = self.session.preview_pair(
            lambda content, project: (transform(content), project),
            kind="r8-advanced", mission_id=mission_id,
            views=("workspace", "inspector"),
        )
        return self.session.apply(plan)

    def jobs(self):
        return tuple(sorted(self._content().get("jobs", {})))

    def class_graph(self):
        return class_ai_authoring.job_graph(self._content())

    def talent_graph(self, job_id):
        return class_ai_authoring.talent_graph(self._content(), job_id)

    def talents(self, job_id):
        jobs = self._content().get("jobs", {})
        require(job_id in jobs, "Unknown job")
        return deepcopy(jobs[job_id].get("talents", {}))

    def save_talent(self, job_id, talent_id, *, jp=1, requires=(),
                    exclusive="", bonuses=None, skills=(), creating=False):
        """Do not bypass canonical DAG, skill ID, JP and exclusive validation."""
        spec = class_ai_authoring.make_talent(
            jp=jp, requires=tuple(requires), exclusive=exclusive,
            bonuses=deepcopy(bonuses or {}), skills=tuple(skills))
        return self._edit(lambda data: class_ai_authoring.save_talent(
            data, job_id, talent_id, spec, creating=creating))

    def remove_talent(self, job_id, talent_id):
        return self._edit(lambda data: class_ai_authoring.delete_talent(
            data, job_id, talent_id))

    def link_class(self, job_id, requires="", level=1):
        return self._edit(lambda data: class_ai_authoring.link_job(
            data, job_id, requires, level))

    def missions(self):
        return tuple((mission["id"], mission["name"])
                     for mission in self._content()["missions"])

    def mission(self, mission_id):
        for row in self._content()["missions"]:
            if row["id"] == mission_id:
                return deepcopy(row)
        raise RuleError("Unknown mission")

    def units(self, mission_id):
        mission = self.mission(mission_id)
        return tuple(EncounterUnit(
            row["id"], row["name"], row["team"],
            row["pos"][0], row["pos"][1],
            row.get("archetype", ""), row.get("weapon", "melee"),
        ) for row in mission["units"])

    def add_actor(self, mission_id, archetype_id, unit_id, *, name,
                  team="enemy", cell):
        """Place a real Content archetype. No linked mutable actor instances."""
        require(team in ("player", "enemy"), "Invalid encounter team")
        return self._edit(lambda data: actor_catalog.place_archetype(
            data, mission_id, archetype_id, unit_id, name, team,
            list(cell)), mission_id=mission_id)

    def move_actor(self, mission_id, unit_id, cell):
        return self._edit(lambda data: entity_editing.relocate_entity(
            data, mission_id, "actor", unit_id, list(cell)),
            mission_id=mission_id)

    def remove_actor(self, mission_id, unit_id):
        """Canonical validator rejects deleting the last member of either team."""
        return self._edit(lambda data: entity_editing.remove_entity(
            data, mission_id, "actor", unit_id),
            mission_id=mission_id)

    def set_formation(self, mission_id, unit_id, *, role="none",
                      formation="none", escort_target=""):
        """Reuse the canonical role/formation command and preserve other tags."""
        return self._edit(lambda data: authoring.set_unit_combat_role(
            data, mission_id, unit_id, role=role, formation=formation,
            escort_target=escort_target), mission_id=mission_id)

    def set_objective(self, mission_id, objective, reward):
        mission = self.mission(mission_id)
        return self._edit(lambda data: authoring.set_mission_properties(
            data, mission_id, name=mission["name"], objective=objective,
            reward=reward, next_missions=mission["next_missions"]),
            mission_id=mission_id)

    def preview(self, mission_id):
        """Pure authoring preview; not a simulated win-rate or combat result."""
        mission = self.mission(mission_id)
        units = self.units(mission_id)
        blocked = {tuple(tile["pos"])
                   for tile in mission["board"].get("tiles", [])
                   if tile.get("blocked", False)}
        return {
            "mission_id": mission_id,
            "name": mission["name"],
            "width": mission["board"]["width"],
            "height": mission["board"]["height"],
            "objective": mission["objective"],
            "reward": mission["reward"],
            "players": sum(u.team == "player" for u in units),
            "enemies": sum(u.team == "enemy" for u in units),
            "blocked_cells": len(blocked),
            "actors": tuple(units),
        }

    def undo(self):
        return self.session.undo()

    def redo(self):
        return self.session.redo()
