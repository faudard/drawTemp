"""R8: headless RPG database facade over the canonical Content/GameProject documents.

All writes use AuthoringSession's validated revisioned transactions.  The
legacy character/actor commands remain the single implementation of rules;
this module does not introduce a database or a second serialization format.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

from drawtemp.sdk.authoring import AuthoringSession
from sporebound import actor_catalog as actors
from sporebound import character_authoring as rules
from sporebound import class_ai_authoring as progress
from sporebound.model import Content, RuleError, require


FAMILIES = ("archetypes", "actors", "jobs", "skills", "equipment", "flags")
EDITABLE = frozenset(FAMILIES) - {"flags"}
LABELS = {
    "archetypes": "Modèles / bestiaire", "actors": "Unités placées",
    "jobs": "Classes et métiers", "skills": "Compétences",
    "equipment": "Équipements", "flags": "Variables utilisées",
}


@dataclass(frozen=True)
class Entry:
    family: str
    id: str
    name: str
    mission_id: str = ""


def _data(snapshot):
    return snapshot.to_dict()


def inventory(content, project):
    """Stable index of existing resources; never stores a shadow registry."""
    entries = []
    for key, row in sorted(content.get("archetypes", {}).items()):
        entries.append(Entry("archetypes", key, row.get("name", key)))
    for mission in content["missions"]:
        for unit in mission["units"]:
            entries.append(Entry("actors", unit["id"], unit.get("name", unit["id"]),
                                 mission["id"]))
    for key, row in sorted(content.get("jobs", {}).items()):
        entries.append(Entry("jobs", key, row.get("name", key)))
    for row in content["skills"]:
        entries.append(Entry("skills", row["id"], row["name"]))
    for key, row in sorted(content.get("equipment", {}).items()):
        entries.append(Entry("equipment", key, row.get("name", key)))
    entries.extend(Entry("flags", key, key) for key in sorted(used_flags(project)))
    return tuple(entries)


def used_flags(project):
    """Collect existing narrative condition/effect flags, not synthetic schema."""
    result = set()
    def visit(node):
        if isinstance(node, dict):
            flag = node.get("flag")
            if isinstance(flag, str) and flag:
                result.add(flag)
            for value in node.values():
                visit(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                visit(value)
    visit(project.get("story", {}))
    visit(project.get("campaign_flow", {}))
    visit(project.get("battle_support", []))
    return result


def referrers(content, project, family, identifier):
    """Find direct semantic references used for safe deletion and inspection."""
    results = []
    for mission in content["missions"]:
        mid = mission["id"]
        for unit in mission["units"]:
            if family == "archetypes" and unit.get("archetype") == identifier:
                results.append(f"mission/{mid}/actor/{unit['id']}")
            if family == "skills" and identifier in unit.get("skills", []):
                results.append(f"mission/{mid}/actor/{unit['id']}/skills")
        if family == "archetypes":
            for trigger in mission.get("triggers", []):
                for action in trigger.get("actions", []):
                    candidates = [action.get("actor", {})] + action.get("actors", [])
                    if any(isinstance(actor, dict) and
                           actor.get("archetype") == identifier for actor in candidates):
                        results.append(f"mission/{mid}/trigger/{trigger['id']}")
    for key, row in content.get("archetypes", {}).items():
        if family == "skills" and identifier in row.get("skills", []):
            results.append(f"archetype/{key}/skills")
    for key, row in content.get("jobs", {}).items():
        if family == "jobs" and row.get("requires") == identifier:
            results.append(f"job/{key}/requires")
        if family == "skills" and identifier in row.get("skills", {}):
            results.append(f"job/{key}/skills")
        if family == "skills":
            for tid, talent in row.get("talents", {}).items():
                if identifier in talent.get("skills", []):
                    results.append(f"job/{key}/talent/{tid}/skills")
    # Story references are structural: a grant/equip uses an equipment ID.
    if family == "equipment":
        for scene in project.get("story", {}).get("scenes", []):
            for choice in scene.get("choices", []):
                for effect in choice.get("effects", []):
                    if effect.get("item") == identifier:
                        results.append(f"story/{scene['id']}/{choice['id']}/item")
    return tuple(results)


def _resource(content, family, identifier, mission_id=""):
    if family == "actors":
        for mission in content["missions"]:
            if mission["id"] == mission_id:
                for unit in mission["units"]:
                    if unit["id"] == identifier:
                        return unit
        raise RuleError("Unité ou mission inconnue")
    if family == "skills":
        for row in content["skills"]:
            if row["id"] == identifier:
                return row
        raise RuleError("Compétence inconnue")
    if family in ("archetypes", "jobs", "equipment"):
        try:
            return content[family][identifier]
        except KeyError as exc:
            raise RuleError("Ressource inconnue") from exc
    raise RuleError("Famille non éditable")


def _transform(content, family, operation, identifier, mission_id="", **kwargs):
    if operation == "duplicate":
        new_id = kwargs["new_id"]
        source = deepcopy(_resource(content, family, identifier))
        if family == "archetypes":
            result = actors.create_archetype(
                content, new_id, kind=source.get("kind", "character"))
            result["archetypes"][new_id] = source
        elif family == "jobs":
            result = rules.create_job(content, new_id, source["name"] + " (copie)")
            result["jobs"][new_id] = {**source, "name": source["name"] + " (copie)"}
        elif family == "equipment":
            result = rules.create_equipment(content, new_id,
                                            source["name"] + " (copie)",
                                            source["slot"])
            result["equipment"][new_id] = {**source, "name": source["name"] + " (copie)"}
        elif family == "skills":
            result = rules.create_skill(content, new_id,
                                        source["name"] + " (copie)")
            index = next(i for i, row in enumerate(result["skills"])
                         if row["id"] == new_id)
            result["skills"][index] = {**source, "id": new_id,
                                       "name": source["name"] + " (copie)"}
        else:
            raise RuleError("Only reusable definitions can be duplicated")
        return result
    if operation == "create":
        if family == "archetypes":
            return actors.create_archetype(content, identifier, **kwargs)
        if family == "jobs":
            return rules.create_job(content, identifier, **kwargs)
        if family == "skills":
            return rules.create_skill(content, identifier, **kwargs)
        if family == "equipment":
            return rules.create_equipment(content, identifier, **kwargs)
        if family == "actors":
            return actors.place_archetype(content, mission_id,
                                          kwargs["archetype"], identifier,
                                          kwargs["name"], kwargs["team"], kwargs["pos"])
    if family == "skills" and operation == "effect":
        return rules.set_skill_effect(content, identifier, kwargs["index"],
                                      kwargs["effect"], insert=kwargs.get("insert", False))
    if family == "skills" and operation == "remove_effect":
        return rules.remove_skill_effect(content, identifier, kwargs["index"])
    if family == "skills" and operation == "move_effect":
        return rules.move_skill_effect(content, identifier, kwargs["index"], kwargs["direction"])
    if operation == "update":
        if family == "archetypes":
            return rules.update_archetype(content, identifier, **kwargs)
        if family == "actors":
            return rules.update_mission_unit(content, mission_id, identifier, **kwargs)
        if family == "jobs":
            if "requires" in kwargs or "requires_level" in kwargs:
                row = content["jobs"][identifier]
                content = progress.link_job(content, identifier,
                    kwargs.get("requires", row.get("requires", "")),
                    kwargs.get("requires_level", row.get("requires_level", 1)))
            return rules.update_job(content, identifier, **kwargs)
        if family == "skills":
            return rules.update_skill(content, identifier, **kwargs)
        if family == "equipment":
            return rules.update_equipment(content, identifier, **kwargs)
    if operation == "remove":
        if family == "archetypes":
            return actors.remove_archetype(content, identifier)
        if family == "jobs":
            return rules.remove_job(content, identifier)
        if family == "skills":
            return rules.remove_skill(content, identifier)
        if family == "equipment":
            return rules.remove_equipment(content, identifier)
    raise RuleError("Opération non disponible pour cette famille")


class DatabaseEditor:
    """UI-neutral adapter: every command commits at most one history entry."""

    def __init__(self, session: AuthoringSession):
        if not isinstance(session, AuthoringSession):
            raise TypeError("Expected AuthoringSession")
        self.session = session

    def snapshot(self):
        return self.session.snapshot()

    def entries(self, family="", search=""):
        if family and family not in FAMILIES:
            raise RuleError("Famille inconnue")
        pair = _data(self.snapshot())
        term = search.casefold().strip()
        return tuple(row for row in inventory(pair["content"], pair["project"])
                     if (not family or row.family == family) and
                     (not term or term in (row.id + " " + row.name + " " +
                                           row.mission_id).casefold()))

    def detail(self, family, identifier, mission_id=""):
        pair = _data(self.snapshot())
        if family == "flags":
            require(identifier in used_flags(pair["project"]), "Unknown flag")
            return {"id": identifier, "read_only": True}
        return deepcopy(_resource(pair["content"], family, identifier, mission_id))

    def references(self, family, identifier):
        pair = _data(self.snapshot())
        return referrers(pair["content"], pair["project"], family, identifier)

    def preview_many(self, actions):
        """Preview a batch atomically, with the SDK's stale-revision protection.

        actions = ((family, operation, id, mission_id, kwargs), ...).
        """
        actions = tuple(actions)
        require(bool(actions), "No changes requested")
        def change(content, project):
            for family, op, key, mission, fields in actions:
                require(family in EDITABLE and isinstance(fields, dict),
                        "Invalid database action")
                if op == "remove":
                    refs = referrers(content, project, family, key)
                    require(not refs, "Ressource utilisée : " + ", ".join(refs))
                content = _transform(content, family, op, key, mission,
                                     **deepcopy(fields))
            return content, project
        return self.session.preview_pair(
            change, kind="rpg-database",
            views=("workspace", "inspector"),
        )

    def commit(self, plan):
        return self.session.apply(plan)

    def apply_many(self, actions):
        return self.commit(self.preview_many(actions))

    def create(self, family, identifier, *, mission_id="", **fields):
        return self.apply_many(((family, "create", identifier, mission_id, fields),))

    def update(self, family, identifier, *, mission_id="", **fields):
        return self.apply_many(((family, "update", identifier, mission_id, fields),))

    def remove(self, family, identifier):
        return self.apply_many(((family, "remove", identifier, "", {}),))

    def duplicate(self, family, identifier, new_id):
        require(family in {"archetypes", "jobs", "skills", "equipment"},
                "Only reusable definitions can be duplicated")
        return self.apply_many(((family, "duplicate", identifier, "",
                                 {"new_id": new_id}),))

    def set_effect(self, skill_id, index, effect, *, insert=False):
        return self.apply_many((("skills", "effect", skill_id, "",
                                 {"index": index, "effect": effect,
                                  "insert": insert}),))

    def remove_effect(self, skill_id, index):
        return self.apply_many((("skills", "remove_effect", skill_id, "",
                                 {"index": index}),))

    def move_effect(self, skill_id, index, direction):
        return self.apply_many((("skills", "move_effect", skill_id, "",
                                 {"index": index, "direction": direction}),))

    def _content_command(self, change: Callable):
        return self.session.apply(self.session.preview_pair(
            lambda content, project: (change(content), project),
            kind="rpg-database", views=("workspace", "inspector")))

    def link_job(self, job_id, prerequisite, level=1):
        return self._content_command(
            lambda data: progress.link_job(data, job_id, prerequisite, level))

    def undo(self):
        return self.session.undo()

    def redo(self):
        return self.session.redo()

    def save(self):
        return self.session.save()

    def save_as(self, path):
        return self.session.save_as(path)


def lancer_example(session: AuthoringSession):
    """R8 acceptance fixture: validated lancer/guard setup in ONE transaction.

    Reusable class, spear equipment and protect-status skill use real runtime
    contracts. Template does not silently change pre-existing mission actors.
    """
    editor = DatabaseEditor(session)
    editor.apply_many((
        ("skills", "create", "r8_guard_ally", "", {
            "name": "Garde protectrice", "target": "ally", "range": 1, "cost": 3,
            "effect": rules.make_effect("status", power=1, status="protect", duration=24),
        }),
        ("jobs", "create", "r8_lancier", "", {
            "name": "Lancier", "skills": {"r8_guard_ally": 1},
            "bonuses": {"defense": 2},
        }),
        ("equipment", "create", "r8_spear", "", {
            "name": "Lance de garde", "slot": "weapon", "price": 90,
            "bonuses": {"weapon_power": 3},
        }),
        ("archetypes", "create", "r8_lancier", "", {
            "kind": "character", "max_hp": 58, "attack": 7, "speed": 9,
            "move": 4, "weapon": "spear", "skills": ["r8_guard_ally"],
        }),
    ))
    return editor
