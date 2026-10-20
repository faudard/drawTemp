"""R62.B.2: typed social authoring through canonical R1 AuthoringSession."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.relationship_life import EXTENSION, validate_relationships
from sporebound.living_world import EXTENSION as WORLD_EXTENSION
from sporebound.system_design import EXTENSION as SYSTEMS_EXTENSION
from sporebound.model import require


def empty_relationships():
    return {"version": 1, "relationships": []}


def _context(session):
    snap = session.snapshot().to_dict()
    project = snap["project"]
    extensions = project.get("extensions", {})
    world = extensions.get(WORLD_EXTENSION)
    if world is None:
        raise ValueError("R62 social authoring requires an existing R35 NPC schedule")
    npcs = world["data"]["npcs"]
    activities = {row["id"]: {stop["activity"] for stop in row["schedule"]}
                  for row in npcs}
    equipment = snap["content"].get("equipment", [])
    items = ({row["id"] for row in equipment}
             if type(equipment) is list else set(equipment))
    systems = extensions.get(SYSTEMS_EXTENSION)
    if systems is not None:
        items.update(row["id"] for row in systems["data"]["resources"])
    return snap, extensions, activities, items


@dataclass(frozen=True)
class RelationshipPreview:
    plan: object
    report: dict


def preview_relationship_design(session, document, *, expected_revision=None):
    if not isinstance(session, AuthoringSession):
        raise TypeError("Expected AuthoringSession")
    snap, extensions, activities, items = _context(session)
    if expected_revision is not None and (
            type(expected_revision) is not int or
            expected_revision != snap["revision"]):
        raise ValueError("Outdated R62 relationship editor revision")
    validated = validate_relationships(
        document, set(activities), items, npc_activities=activities)
    def edit(project):
        project.setdefault("extensions", {})[EXTENSION] = {
            "schema_version": 1, "data": deepcopy(validated), "references": []}
        return project
    plan = session.preview_project(edit, kind="r62.relationships.author")
    return RelationshipPreview(plan, {
        "source_revision": snap["revision"],
        "before_enabled": EXTENSION in extensions,
        "npc_count": len(validated["relationships"]),
        "gift_count": sum(len(row["gifts"])
                          for row in validated["relationships"]),
    })


def apply_relationship_design(session, preview):
    if not isinstance(preview, RelationshipPreview):
        raise TypeError("Expected a validated R62 social preview")
    return session.apply(preview.plan)


class RelationshipDraft:
    """Typed NPC/gift CRUD, local bounded history, one canonical apply."""

    def __init__(self, session, *, history_limit=50):
        require(isinstance(session, AuthoringSession)
                and type(history_limit) is int and 1 <= history_limit <= 100,
                "Invalid R62 social editor session or history limit")
        self.session = session
        snap, extensions, activities, items = _context(session)
        self.revision = snap["revision"]
        self.activities = deepcopy(activities)
        self.npcs = sorted(activities)
        self.items = sorted(items)
        authored = extensions.get(EXTENSION)
        self._states = [deepcopy(authored["data"])
                        if authored is not None else empty_relationships()]
        self._index = 0
        self._limit = history_limit
        self.validate()

    @property
    def document(self):
        return deepcopy(self._states[self._index])

    @property
    def can_undo(self):
        return self._index > 0

    @property
    def can_redo(self):
        return self._index + 1 < len(self._states)

    def validate(self):
        return validate_relationships(
            self.document, set(self.npcs), set(self.items),
            npc_activities=self.activities)

    def upsert(self, row, *, original_npc=None):
        require(type(row) is dict and type(row.get("npc")) is str,
                "Invalid R62 relationship entry")
        proposed = self.document
        entries = proposed["relationships"]
        if original_npc is None:
            require(all(item["npc"] != row["npc"] for item in entries),
                    "NPC relationship already authored")
            entries.append(deepcopy(row))
        else:
            require(row["npc"] == original_npc, "NPC rename needs a migration")
            index = next((i for i, item in enumerate(entries)
                          if item["npc"] == original_npc), -1)
            require(index >= 0, "NPC relationship no longer exists")
            entries[index] = deepcopy(row)
        return self._commit(proposed)

    def remove(self, npc):
        proposed = self.document
        old = proposed["relationships"]
        proposed["relationships"] = [
            row for row in old if row["npc"] != npc]
        require(len(proposed["relationships"]) != len(old),
                "R62 social NPC not found")
        return self._commit(proposed)

    def _commit(self, document):
        validated = validate_relationships(
            document, set(self.npcs), set(self.items),
            npc_activities=self.activities)
        if validated == self._states[self._index]:
            return False
        self._states = self._states[:self._index + 1]
        self._states.append(validated)
        if len(self._states) > self._limit + 1:
            self._states.pop(0)
        self._index = len(self._states) - 1
        return True

    def undo(self):
        if not self.can_undo:
            return False
        self._index -= 1
        return True

    def redo(self):
        if not self.can_redo:
            return False
        self._index += 1
        return True

    def preview(self):
        return preview_relationship_design(
            self.session, self.document, expected_revision=self.revision)

    def apply(self):
        transition = apply_relationship_design(self.session, self.preview())
        self.revision = transition.snapshot.revision
        self._states = [self.document]
        self._index = 0
        return transition


__all__ = ["RelationshipDraft", "RelationshipPreview", "empty_relationships",
           "preview_relationship_design", "apply_relationship_design"]
