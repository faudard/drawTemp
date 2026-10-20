"""R37.E2 — canonical R1 boss director authoring, no duplicate phase scripts.

This authoring facade edits only R37 presentation metadata. New real boss
abilities, transitions and reinforcements must first be authored in existing
Content/Mission triggers; the designer cannot invent executable combat data.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.advanced_ai import EXTENSION
from sporebound.ai_boss_director import (
    _scripted_transitions, _starting_phase, validate_boss_directors)
from sporebound.model import Content, require
from sporebound.tactical_rpg3 import authored_rules_for_document


class BossDirectorDesigner:
    def __init__(self, session):
        if not isinstance(session, AuthoringSession):
            raise TypeError("Expected the canonical R1 AuthoringSession")
        self.session = session

    def _snapshot(self):
        return self.session.snapshot().to_dict()

    def _content(self):
        document = self._snapshot()["content"]
        return Content.from_dict(document, rules=authored_rules_for_document(document))

    def catalog(self):
        project = self._snapshot()["project"]
        extension = project.get("extensions", {}).get(EXTENSION)
        return deepcopy(extension["data"].get("boss_directors", [])
                        if extension is not None else [])

    def choices(self):
        content = self._content()
        return [
            {"mission": mission.id, "boss": actor.id}
            for mission in sorted(content.missions.values(), key=lambda m: m.id)
            for actor in sorted(mission.units, key=lambda u: u.id)
            if actor.team == "enemy" and
            actor.behavior in ("phase_boss", "adaptive_boss")]

    def suggest(self, mission_id, boss_id):
        """Derive all phases from ACTUAL authored boss_phase triggers."""
        content = self._content()
        require(type(mission_id) is str and mission_id in content.missions,
                "Unknown boss mission")
        mission = content.missions[mission_id]
        boss = next((unit for unit in mission.units if unit.id == boss_id
                     and unit.team == "enemy"
                     and unit.behavior in ("phase_boss", "adaptive_boss")), None)
        require(boss is not None, "Actor is not an authored R6 boss")
        initial = _starting_phase(boss)
        authored = _scripted_transitions(mission, boss_id)
        numbers = [initial] + sorted(authored)
        require(numbers == list(range(initial, initial + len(numbers))),
                "Existing R6 boss phase progression is discontinuous")
        rows = [{
            "phase": num,
            "label": "Phase " + str(num),
            "cue": "",
            "trigger": None if num == initial else authored[num]["trigger"],
        } for num in numbers]
        import re
        safe_id = re.sub(r"[^a-z0-9_]", "_", boss_id.lower())
        suggestion = {
            "id": ("boss_" + safe_id)[:64],
            "mission": mission_id, "boss": boss_id, "phases": rows}
        validate_boss_directors([suggestion], content=content)
        return suggestion

    def preview_catalog(self, directors, *, expected_revision=None):
        if expected_revision is not None and expected_revision != self.session.revision:
            raise ValueError("Stale R37 boss director revision")
        content = self._content()
        validated = (validate_boss_directors(directors, content=content)
                     if directors else [])

        def update(project):
            extension = project.get("extensions", {}).get(EXTENSION)
            if extension is None:
                raise ValueError("Create the canonical R37 AI extension first")
            if validated:
                extension["data"]["boss_directors"] = deepcopy(validated)
            else:
                extension["data"].pop("boss_directors", None)
            return project

        return self.session.preview_project(update, kind="r37.boss-director")

    def preview_add(self, mission_id, boss_id, *, expected_revision=None):
        catalog = self.catalog()
        candidate = self.suggest(mission_id, boss_id)
        if any(item["mission"] == mission_id and item["boss"] == boss_id
               for item in catalog):
            raise ValueError("Boss already has a director for this encounter")
        used_ids = {item["id"] for item in catalog}
        if candidate["id"] in used_ids:
            for num in range(2, 100):
                ident = candidate["id"][:61] + str(num)
                if ident not in used_ids:
                    candidate["id"] = ident
                    break
            else:
                raise ValueError("No free R37 boss director ID")
        catalog.append(candidate)
        return self.preview_catalog(catalog, expected_revision=expected_revision)

    def preview_phase(self, director_id, phase, *, label, cue="",
                      expected_revision=None):
        catalog = self.catalog()
        director = next((item for item in catalog
                         if item["id"] == director_id), None)
        if director is None:
            raise ValueError("Unknown R37 boss director")
        row = next((item for item in director["phases"]
                    if item["phase"] == phase), None)
        if row is None:
            raise ValueError("Unknown authored boss phase")
        row["label"], row["cue"] = label, cue
        return self.preview_catalog(catalog, expected_revision=expected_revision)

    def preview_remove(self, director_id, *, expected_revision=None):
        rows = self.catalog()
        filtered = [row for row in rows if row["id"] != director_id]
        if len(rows) == len(filtered):
            raise ValueError("Unknown R37 boss director")
        return self.preview_catalog(filtered, expected_revision=expected_revision)

    def apply(self, plan):
        return self.session.apply(plan)
