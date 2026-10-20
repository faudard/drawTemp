"""R45.B: one economy authoring draft on the R1 AuthoringSession.

There is no economic sidecar or second undo stack. All changes are staged as
one replacement of GameProject's R35 living-world document, validated by the
canonical Content + GameProject pair before an atomic apply.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.living_world_authoring import (
    apply_living_world, preview_living_world,
)
from sporebound.living_world import EXTENSION


class EconomyDraft:
    def __init__(self, session: AuthoringSession):
        if not isinstance(session, AuthoringSession):
            raise TypeError("Expected the active AuthoringSession")
        self.session = session
        snapshot = session.snapshot()
        self.revision = snapshot.revision
        pair = snapshot.to_dict()
        envelope = pair["project"].get("extensions", {}).get(EXTENSION)
        self.document = deepcopy(envelope["data"]) if envelope else {
            "version": 1,
            "start_minute": 480,
            "ticks_per_minute": 60,
            "clock_policy": "exploration_only",
            "npcs": [],
        }
        self.scenes = sorted(
            set(pair["project"].get("exploration", {})) |
            {m["id"] for m in pair["content"]["missions"]})
        self.equipment_ids = sorted(pair["content"].get("equipment", {}))

    def item_ids(self):
        return sorted(set(self.equipment_ids) | {
            item["id"] for shop in self.document.get("shops", [])
            for item in shop["items"]})

    def _upsert(self, key, value, original_id=None):
        if type(value) is not dict or type(value.get("id")) is not str:
            raise ValueError("Missing catalogue record identity")
        entries = self.document.setdefault(key, [])
        if original_id is None:
            if any(item["id"] == value["id"] for item in entries):
                raise ValueError("This identity already exists")
            entries.append(deepcopy(value))
        else:
            if value["id"] != original_id:
                raise ValueError("Renaming a referenced ID requires a separate migration")
            index = next((i for i, item in enumerate(entries)
                          if item["id"] == original_id), -1)
            if index < 0:
                raise ValueError("The selected record no longer exists")
            entries[index] = deepcopy(value)

    def upsert_shop(self, value, *, original_id=None):
        self._upsert("shops", value, original_id)

    def upsert_recipe(self, value, *, original_id=None):
        self._upsert("recipes", value, original_id)

    def _remove(self, key, record_id):
        items = self.document.get(key, [])
        remaining = [row for row in items if row["id"] != record_id]
        if len(remaining) == len(items):
            raise ValueError("Unknown catalogue record")
        self.document[key] = remaining

    def remove_shop(self, shop_id):
        self._remove("shops", shop_id)

    def remove_recipe(self, recipe_id):
        self._remove("recipes", recipe_id)

    def preview(self):
        """This does not mutate the session or advance its revision."""
        return preview_living_world(
            self.session, self.document, expected_revision=self.revision)

    def apply(self):
        """Refuses stale drafts; one commit and one undo step on success."""
        return apply_living_world(self.session, self.preview())
