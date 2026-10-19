"""Typed, transactional property editor for the R2 Qt inspector.

This module deliberately imports neither Qt nor Tk. A selected field is
resolved from the canonical two-document snapshot at the instant of preview;
no resource ID is rewritten, and multi-selection is one R1 history entry.
"""
from __future__ import annotations

from dataclasses import dataclass

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.studio.workspace_model import Resource


@dataclass(frozen=True)
class PropertySpec:
    key: str
    label: str
    kind: str
    minimum: int = 0
    maximum: int = 0
    choices: tuple[str, ...] = ()


COMMON = (PropertySpec("name", "Nom", "text"),)
SCHEMAS = {
    "project": (PropertySpec("title", "Titre du projet", "text"),),
    "maps": COMMON + (
        PropertySpec("reward", "Récompense", "int", 0, 1000000),
        PropertySpec("target_ticks", "Durée limite (ticks)", "int", 1, 100000),
    ),
    "actors": COMMON + (
        PropertySpec("max_hp", "Points de vie", "int", 1, 9999),
        PropertySpec("attack", "Attaque", "int", 0, 9999),
        PropertySpec("speed", "Vitesse", "int", 1, 9999),
        PropertySpec("move", "Déplacement", "int", 0, 99),
    ),
    "objects": COMMON + (PropertySpec("amount", "Quantité", "int", 0, 10000),),
    "campaigns": COMMON,
    "scenes": (
        PropertySpec("title", "Titre du dialogue", "text"),
        PropertySpec("speaker", "Intervenant", "text"),
        PropertySpec("text", "Dialogue", "multiline"),
    ),
    "cinematics": COMMON,
}
DOOR = (
    PropertySpec("hp", "Résistance de porte", "int", 1, 10000),
    PropertySpec("locked", "Porte verrouillée", "bool"),
)
DEFAULTS = {"maps": {"reward": 100, "target_ticks": 100},
            "objects": {"name": "", "amount": 1, "hp": 1, "locked": False}}


class InspectorError(ValueError):
    """Property-level validation failure suitable for inline UI feedback."""


def _pair(snapshot):
    return snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot


def _find(entries, identifier):
    return next((row for row in entries if row["id"] == identifier), None)


def _resolve(pair, resource: Resource):
    content, project = pair["content"], pair["project"]
    if resource.family == "project":
        if resource.resource_id != "project":
            raise InspectorError("Projet introuvable")
        return project
    if resource.family in ("maps", "actors", "objects", "events"):
        mission_id = resource.resource_id if resource.family == "maps" else resource.mission_id
        mission = _find(content["missions"], mission_id)
        if mission is None:
            raise InspectorError("Carte absente : " + mission_id)
        if resource.family == "maps":
            return mission
        field = {"actors": "units", "objects": "objects",
                 "events": "triggers"}[resource.family]
        result = _find(mission.get(field, []), resource.resource_id)
    else:
        field = {"campaigns": "campaigns", "scenes": "scenes",
                 "cinematics": "cinematics"}.get(resource.family)
        if field is None:
            raise InspectorError("Famille inconnue : " + resource.family)
        rows = (project.get("story", {}).get("scenes", [])
                if field == "scenes" else project.get(field, []))
        result = _find(rows, resource.resource_id)
    if result is None:
        raise InspectorError("Ressource absente : " + resource.resource_id)
    return result


def specs_for(pair, resource):
    item = _resolve(pair, resource)
    specs = SCHEMAS.get(resource.family, ())
    if resource.family == "objects" and item.get("kind") == "door":
        specs += DOOR
    # Only show fields actually present, except canonical documented defaults.
    defaults = DEFAULTS.get(resource.family, {})
    return tuple(spec for spec in specs
                 if spec.key in item or spec.key in defaults)


def shared_specs(snapshot, selected):
    """Intersection for multi-selection; no ambiguous field-type coercion."""
    selected = tuple(selected)
    if not selected:
        return ()
    pair = _pair(snapshot)
    per = [specs_for(pair, resource) for resource in selected]
    return tuple(spec for spec in per[0] if all(spec in group for group in per[1:]))


def common_value(snapshot, selected, key):
    """(value, mixed). None is never interpreted as an edit instruction."""
    selected = tuple(selected)
    pair = _pair(snapshot)
    valid = {spec.key for spec in shared_specs(pair, selected)}
    if key not in valid:
        raise InspectorError("Champ indisponible : " + key)
    values = [
        _resolve(pair, resource).get(
            key, resource.resource_id if key == "name" else
            DEFAULTS.get(resource.family, {}).get(key))
        for resource in selected
    ]
    first = values[0]
    return first, any(value != first for value in values[1:])


def _coerce(spec: PropertySpec, value):
    if spec.kind == "bool":
        if type(value) is not bool:
            raise InspectorError(spec.label + " : booléen attendu")
        return value
    if spec.kind == "int":
        if type(value) is not int or not spec.minimum <= value <= spec.maximum:
            raise InspectorError(
                f"{spec.label} : entier entre {spec.minimum} et {spec.maximum}")
        return value
    if spec.kind in ("text", "multiline"):
        if not isinstance(value, str):
            raise InspectorError(spec.label + " : texte attendu")
        if not value.strip() or len(value) > (10000 if spec.kind == "multiline" else 255):
            raise InspectorError(spec.label + " : texte vide ou trop long")
        return value.strip() if spec.kind == "text" else value
    if spec.kind == "enum":
        if value not in spec.choices:
            raise InspectorError(spec.label + " : valeur non autorisée")
        return value
    raise InspectorError("Type de propriété non pris en charge")


def validate_draft(snapshot, selected, updates):
    """Type-check only edited fields, for immediate per-field UI feedback.

    Returns (typed_values, errors_by_field) without mutating or previewing
    documents. Cross-field and canonical constraints remain enforced by the
    atomic R1 preview/apply on commit.
    """
    selected = tuple(selected)
    if not selected:
        raise InspectorError("Aucune ressource sélectionnée")
    if len({item.key for item in selected}) != len(selected):
        raise InspectorError("Sélection dupliquée")
    specs = {spec.key: spec for spec in shared_specs(snapshot, selected)}
    typed, errors = {}, {}
    for key, value in updates.items():
        if key not in specs:
            errors[key] = "Champ indisponible : " + key
            continue
        try:
            typed[key] = _coerce(specs[key], value)
        except InspectorError as exc:
            errors[key] = str(exc)
    return typed, errors


def preview_properties(session: AuthoringSession, selected, updates,
                       *, expected_revision=None):
    """Create a single preview; caller may inspect or apply it atomically."""
    selected = tuple(selected)
    if not selected or not updates:
        raise InspectorError("Aucune modification demandée")
    if len({r.key for r in selected}) != len(selected):
        raise InspectorError("Sélection dupliquée")
    snapshot = session.snapshot()
    if expected_revision is not None and snapshot.revision != expected_revision:
        raise InspectorError("La sélection a changé : rafraîchissez l'inspecteur")
    typed, errors = validate_draft(snapshot, selected, updates)
    if errors:
        raise InspectorError("; ".join(errors[key] for key in sorted(errors)))

    def transform(content, project):
        pair = {"content": content, "project": project}
        for resource in selected:
            target = _resolve(pair, resource)
            for key, value in typed.items():
                target[key] = value
        return content, project

    return session.preview_pair(transform, kind="r2.inspector.properties",
                                views=("workspace", "inspector"))


def edit_properties(session, selected, updates, *, expected_revision=None):
    plan = preview_properties(session, selected, updates,
                              expected_revision=expected_revision)
    return session.apply(plan)
