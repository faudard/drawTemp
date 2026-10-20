"""R43.B1: Qt-free ability drafts, targeting overlay and safe authoring previews.

The canonical data owner is the R43.A GameProject/Content pair. This adapter
holds disposable form state only; no runtime skills or second registry exist.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from drawtemp.sdk.ability_contracts import (
    AbilityError, catalog_from_project, compile_ct_skill, preview_ability,
    resolve_ability, validate_ability,
)
from drawtemp.sdk.authoring import AuthoringSession


def new_ability(identifier="r43_new"):
    """CT-compatible skill template; callers choose other profiles explicitly."""
    return {
        "schema_version": 1, "id": identifier, "name": "Nouvelle compétence",
        "profiles": ["TACTICAL_CT"],
        "cost": {"resource": "mp", "amount": 2},
        "target": {"team": "enemy", "shape": "single",
                   "min_range": 0, "range": 2, "radius": 0},
        "timing": {"TACTICAL_CT": {"windup": 0, "cooldown": 0}},
        "effects": [
            {"kind": "damage", "formula": {"op": "constant", "value": 8},
             "element": "physical", "status": "", "duration": 1,
             "scope": "target"},
        ],
    }


def area_preview(target, *, origin=(4, 4), aim=(4, 3), size=9):
    """A deterministic abstract cell overlay, NOT the native viewport/LOS.

    Out-of-range input is not silently clamped. Affects no Content, Battle,
    ActionRuntime or project data. Picking parity is an R43.C gate.
    """
    if (type(size) is not int or not 3 <= size <= 128 or
            any(type(cell) not in (list, tuple) or len(cell) != 2 or
                any(type(n) is not int or not 0 <= n < size for n in cell)
                for cell in (origin, aim))):
        raise AbilityError("invalid_cell", "Origin and aim must be valid cells")
    if type(target) is not dict or set(target) != {
            "team", "shape", "min_range", "range", "radius"}:
        raise AbilityError("invalid_target", "Expected canonical target fields")
    shape = target["shape"]
    if shape not in ("single", "diamond", "cross", "square"):
        raise AbilityError("invalid_target", "Unsupported footprint")
    for key, low, high in (("min_range", 0, 16), ("range", 0, 16),
                           ("radius", 0, 8)):
        v = target[key]
        if type(v) is not int or not low <= v <= high:
            raise AbilityError("invalid_target", "Invalid target " + key)
    if target["min_range"] > target["range"]:
        raise AbilityError("invalid_target", "Invalid range ordering")
    distance = abs(aim[0] - origin[0]) + abs(aim[1] - origin[1])
    in_range = target["min_range"] <= distance <= target["range"]
    if shape == "single" and target["radius"] != 0:
        raise AbilityError("invalid_target", "Single must use radius zero")
    cells = []
    if in_range:
        r = target["radius"]
        for y in range(max(0, aim[1] - r), min(size - 1, aim[1] + r) + 1):
            for x in range(max(0, aim[0] - r), min(size - 1, aim[0] + r) + 1):
                dx, dy = abs(x - aim[0]), abs(y - aim[1])
                include = (
                    shape == "single" and x == aim[0] and y == aim[1] or
                    shape == "diamond" and dx + dy <= r or
                    shape == "cross" and (dx == 0 or dy == 0) and max(dx, dy) <= r or
                    shape == "square" and max(dx, dy) <= r
                )
                if include:
                    cells.append([x, y])
    return {"origin": list(origin), "aim": list(aim),
            "size": size, "in_range": in_range, "cells": cells,
            "note": "Aperçu géométrique, hors obstacles, hauteur, équipe et LOS"}


@dataclass(frozen=True)
class AbilityDraftPreview:
    plan: object
    report: dict


class AbilityDraft:
    """Disposable editor buffer; preview/apply require one R1 owner revision."""

    def __init__(self, session: AuthoringSession, document, *, original_id=None):
        if not isinstance(session, AuthoringSession):
            raise TypeError("Expected AuthoringSession")
        self.session = session
        self.source_revision = session.revision
        self.original_id = original_id
        self.document = deepcopy(document)
        self.pending = None

    @classmethod
    def create(cls, session, identifier="r43_new"):
        return cls(session, new_ability(identifier))

    @classmethod
    def load(cls, session, identifier):
        catalog = catalog_from_project(session.snapshot().to_dict()["project"])
        row = next((item for item in catalog["abilities"]
                    if item["id"] == identifier), None)
        if row is None:
            raise AbilityError("missing_ability", "Unknown ability " + str(identifier))
        return cls(session, row, original_id=identifier)

    def set_header(self, *, name, profiles, resource, cost,
                   team, shape, min_range, max_range, radius, timing):
        self.document["name"] = name
        self.document["profiles"] = list(profiles)
        self.document["cost"] = {"resource": resource, "amount": cost}
        self.document["target"] = {
            "team": team, "shape": shape, "min_range": min_range,
            "range": max_range, "radius": radius}
        self.document["timing"] = deepcopy(timing)
        self.pending = None

    def edit_effect(self, index, *, kind, formula, element,
                    status, duration, scope):
        if type(index) is not int or not 0 <= index < len(self.document["effects"]):
            raise AbilityError("invalid_effect", "Effect index outside catalogue")
        self.document["effects"][index] = {
            "kind": kind, "formula": deepcopy(formula), "element": element,
            "status": status, "duration": duration, "scope": scope}
        self.pending = None

    def add_effect(self):
        if len(self.document["effects"]) >= 8:
            raise AbilityError("effect_budget", "Maximum 8 effects per ability")
        self.document["effects"].append(deepcopy(new_ability()["effects"][0]))
        self.pending = None

    def remove_effect(self, index):
        if len(self.document["effects"]) <= 1:
            raise AbilityError("effect_budget", "At least one effect is required")
        if type(index) is not int or not 0 <= index < len(self.document["effects"]):
            raise AbilityError("invalid_effect", "Unknown effect")
        self.document["effects"].pop(index)
        self.pending = None

    def move_effect(self, index, direction):
        if type(index) is not int or type(direction) is not int or direction not in (-1, 1):
            raise AbilityError("invalid_effect", "Expected adjacent effect index")
        other = index + direction
        if not 0 <= index < len(self.document["effects"]) or not 0 <= other < len(self.document["effects"]):
            raise AbilityError("invalid_effect", "Effect cannot move outside list")
        rows = self.document["effects"]
        rows[index], rows[other] = rows[other], rows[index]
        self.pending = None

    def preview(self, *, mode="TACTICAL_CT", stats=None, aim=(4, 3)):
        if self.session.revision != self.source_revision:
            self.pending = None
            raise AbilityError("stale_revision", "Reload after another Studio edit")
        spec = validate_ability(self.document)
        if self.original_id is not None and spec["id"] != self.original_id:
            raise AbilityError("id_change", "Existing ability IDs are immutable")
        if stats is None:
            stats = {"attack": 12, "magic": 12, "defense": 4, "resistance": 4}
        result = resolve_ability(spec, mode=mode, stats=stats)
        footprint = area_preview(spec["target"], aim=aim)
        plan = preview_ability(self.session, spec)
        old = catalog_from_project(self.session.snapshot().to_dict()["project"])
        previous = next((row for row in old["abilities"]
                         if row["id"] == spec["id"]), None)
        if previous == spec:
            self.pending = None
            raise AbilityError("unchanged", "No edited ability fields to apply")
        report = {
            "id": spec["id"], "revision": plan.source_revision,
            "profiles": deepcopy(spec["profiles"]), "mode": mode,
            "before": deepcopy(previous), "after": spec,
            "impact": result, "target_preview": footprint,
            "native_CT": (compile_ct_skill(spec) if "TACTICAL_CT" in spec["profiles"]
                          else None),
            "notes": "Chiffres de formule bruts; non un forecast des dégâts de Battle",
        }
        self.pending = AbilityDraftPreview(plan, report)
        return self.pending

    def apply(self):
        if self.pending is None:
            raise AbilityError("preview_required", "Preview before applying")
        pending = self.pending
        self.pending = None
        result = self.session.apply(pending.plan)
        self.source_revision = self.session.revision
        self.original_id = self.document["id"]
        return result


__all__ = ["new_ability", "area_preview", "AbilityDraft", "AbilityDraftPreview"]
