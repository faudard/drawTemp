"""Typed R9.C authoring catalogue: only registered tactical actions are emitted.

A cinematic or sound cue is not a trigger action: it belongs to GameProject
cinematics, bound to a canonical tactical event by mission/event ID.
"""
from __future__ import annotations

from sporebound.event_composer import action
from sporebound.model import RuleError, require

# One declarative UI contract, not a second runtime schema.
TACTICAL_FIELDS = {
    "message": (("text", "Texte", "text"),),
    "hazard": (("pos", "Case x,y", "cell"), ("amount", "Danger", "integer")),
    "status": (("unit", "Acteur", "text"), ("status", "Statut", "text"),
               ("duration", "Durée", "integer")),
    "despawn": (("unit", "Acteur à retirer", "text"),),
    "spawn": (("actor_id", "ID renfort", "text"),
              ("archetype", "Archétype", "text"), ("name", "Nom", "text"),
              ("team", "Équipe player/enemy", "team"),
              ("pos", "Case x,y", "cell")),
    "wave": (("actor_id", "ID renfort", "text"),
             ("archetype", "Archétype", "text"), ("name", "Nom", "text"),
             ("team", "Équipe player/enemy", "team"),
             ("pos", "Case x,y", "cell"),
             ("max_active", "Maximum actif", "integer")),
    "queue_wave": (("actor_id", "ID renfort", "text"),
                   ("archetype", "Archétype", "text"), ("name", "Nom", "text"),
                   ("team", "Équipe player/enemy", "team"),
                   ("pos", "Case x,y", "cell")),
}


def parse_typed(kind, raw):
    """Parse simple widget values; canonical Content still validates semantics."""
    require(kind in TACTICAL_FIELDS, "Type d'action inconnu")
    require(isinstance(raw, dict), "Champs d'action invalides")
    fields = TACTICAL_FIELDS[kind]
    require(set(raw) == {name for name, _, _ in fields}, "Champs d'action inconnus")
    converted = {}
    for name, _, type_name in fields:
        value = raw[name]
        if type_name == "cell":
            if isinstance(value, str):
                parts = [item.strip() for item in value.split(",")]
                require(len(parts) == 2, "Case attendue : x,y")
                try:
                    value = [int(x) for x in parts]
                except ValueError as exc:
                    raise RuleError("Case attendue : deux entiers") from exc
            require(isinstance(value, (tuple, list)) and len(value) == 2 and
                    all(type(x) is int for x in value), "Case invalide")
            converted[name] = list(value)
        elif type_name == "integer":
            require(type(value) is int or
                    (isinstance(value, str) and value.strip().isdigit()),
                    name + " : entier requis")
            converted[name] = int(value)
        else:
            require(isinstance(value, str) and bool(value.strip()),
                    name + " : texte requis")
            converted[name] = value.strip()
    return converted


def tactical_action(kind, fields):
    """Construct the exact action consumed by the production trigger registry."""
    values = parse_typed(kind, fields)
    return action(kind, **values)


def action_catalogue():
    """UI-readable fields; no Qt or game rules imported by the view."""
    return {kind: tuple(fields) for kind, fields in TACTICAL_FIELDS.items()}
