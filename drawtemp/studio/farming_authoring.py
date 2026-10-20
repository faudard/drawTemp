"""R62.B.1: typed farm authoring over one canonical R1 Studio transaction.

The editor owns only a detached draft. GameProject.extensions remains the
source of truth, the optional R35 clock is never overwritten, and AuthoringSession
provides the authoritative global Undo/Redo and stale-revision protection.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.farming_life import EXTENSION, validate_farming
from sporebound.living_world import EXTENSION as CLOCK_EXTENSION
from sporebound.model import require
from sporebound.system_design import EXTENSION as SYSTEMS_EXTENSION


def empty_farm():
    return {
        "version": 1, "seed": 17, "season_days": 14, "weather": False,
        "plots": [], "crops": [], "animals": [],
    }


def initial_clock():
    """Explicitly requested R35 calendar; does not replace an existing clock."""
    return {
        "version": 1, "start_minute": 480, "ticks_per_minute": 60,
        "clock_policy": "exploration_only", "npcs": [],
    }


@dataclass(frozen=True)
class FarmPreview:
    plan: object
    report: dict


def preview_farm_design(session, document, *, expected_revision=None,
                        initialize_clock=False):
    if not isinstance(session, AuthoringSession):
        raise TypeError("Expected the active AuthoringSession")
    snapshot = session.snapshot().to_dict()
    if expected_revision is not None and (
            type(expected_revision) is not int
            or expected_revision != snapshot["revision"]):
        raise ValueError("Outdated R62 farm designer revision")
    project = snapshot["project"]
    extensions = project.get("extensions", {})
    if CLOCK_EXTENSION not in extensions and not initialize_clock:
        raise ValueError("R62 requires R35: enable the world calendar explicitly")
    scenes = set(project.get("exploration", {}))
    equipment = snapshot["content"].get("equipment", [])
    item_ids = ({row["id"] for row in equipment} if type(equipment) is list
                else set(equipment))
    systems = extensions.get(SYSTEMS_EXTENSION)
    if systems is not None:
        item_ids.update(row["id"] for row in systems["data"]["resources"])
    spec = validate_farming(document, scenes, item_ids)
    before = EXTENSION in extensions

    def edit(draft):
        catalog = draft.setdefault("extensions", {})
        if CLOCK_EXTENSION not in catalog:
            catalog[CLOCK_EXTENSION] = {
                "schema_version": 1, "data": initial_clock(), "references": []}
        catalog[EXTENSION] = {
            "schema_version": 1, "data": deepcopy(spec), "references": []}
        return draft

    plan = session.preview_project(edit, kind="r62.farm.studio")
    return FarmPreview(plan, {
        "revision": snapshot["revision"],
        "previously_enabled": before,
        "clock_initialized": CLOCK_EXTENSION not in extensions,
        "plot_count": len(spec["plots"]),
        "crop_count": len(spec["crops"]),
        "animal_count": len(spec["animals"]),
        "season_days": spec["season_days"],
        "weather_enabled": spec["weather"],
    })


def apply_farm_design(session, preview):
    if not isinstance(preview, FarmPreview):
        raise TypeError("Expected a validated R62 preview")
    return session.apply(preview.plan)


class FarmDraft:
    """Bounded local draft undo/redo, one final canonical project transaction."""

    FAMILIES = ("plots", "crops", "animals")

    def __init__(self, session, *, history_limit=50):
        if not isinstance(session, AuthoringSession):
            raise TypeError("Expected the active AuthoringSession")
        require(type(history_limit) is int and 1 <= history_limit <= 100,
                "Invalid R62 draft history budget")
        self.session = session
        snap = session.snapshot().to_dict()
        self.revision = snap["revision"]
        project = snap["project"]
        extensions = project.get("extensions", {})
        self.scenes = sorted(project.get("exploration", {}))
        equipment = snap["content"].get("equipment", [])
        self.items = sorted({row["id"] for row in equipment}
                            if type(equipment) is list else set(equipment))
        if SYSTEMS_EXTENSION in extensions:
            self.items = sorted(set(self.items) |
                                {row["id"] for row in extensions[SYSTEMS_EXTENSION]
                                 ["data"]["resources"]})
        self.clock_present = CLOCK_EXTENSION in extensions
        self.initialize_clock = False
        authored = extensions.get(EXTENSION)
        self._limit = history_limit
        self._states = [deepcopy(authored["data"]) if authored else empty_farm()]
        self._index = 0
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
        return validate_farming(self.document, set(self.scenes), set(self.items))

    def _commit(self, proposed):
        validated = validate_farming(proposed, set(self.scenes), set(self.items))
        if validated == self._states[self._index]:
            return False
        self._states = self._states[:self._index + 1]
        self._states.append(validated)
        if len(self._states) > self._limit + 1:
            self._states.pop(0)
        self._index = len(self._states) - 1
        return True

    def settings(self, *, seed, season_days, weather):
        proposed = self.document
        proposed.update(seed=seed, season_days=season_days, weather=weather)
        return self._commit(proposed)

    def upsert(self, family, record, *, original_id=None):
        require(family in self.FAMILIES
                and type(record) is dict and type(record.get("id")) is str,
                "Invalid R62 draft family or record")
        proposed = self.document
        entries = proposed[family]
        if original_id is None:
            require(all(row["id"] != record["id"] for row in entries),
                    "R62 identity already exists")
            entries.append(deepcopy(record))
        else:
            require(type(original_id) is str and record["id"] == original_id,
                    "R62 rename needs an explicit migration")
            index = next((i for i, row in enumerate(entries)
                          if row["id"] == original_id), -1)
            require(index >= 0, "R62 selected record is no longer present")
            entries[index] = deepcopy(record)
        return self._commit(proposed)

    def remove(self, family, record_id):
        require(family in self.FAMILIES and type(record_id) is str,
                "Invalid R62 removal")
        proposed = self.document
        entries = proposed[family]
        proposed[family] = [row for row in entries if row["id"] != record_id]
        require(len(proposed[family]) != len(entries),
                "R62 selected record no longer exists")
        return self._commit(proposed)

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
        """Run the canonical GameProject validator without mutating the project."""
        return preview_farm_design(
            self.session, self.document, expected_revision=self.revision,
            initialize_clock=self.initialize_clock)

    def apply(self):
        """One R1 transaction; a stale or invalid preview cannot partially apply."""
        transition = apply_farm_design(self.session, self.preview())
        self.revision = transition.snapshot.revision
        self.clock_present = True
        self.initialize_clock = False
        self._states = [self.document]
        self._index = 0
        return transition


__all__ = ["FarmDraft", "FarmPreview", "empty_farm", "preview_farm_design",
           "apply_farm_design"]
