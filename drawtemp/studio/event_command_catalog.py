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
    # R9.D uses one opt-in canonical action (not in legacy default rules).
    "event_state": (("event", "Événement cible", "text"),
                    ("page", "Page (vide = événement entier)", "optional"),
                    ("enabled", "Activer", "boolean")),
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
        elif type_name == "boolean":
            require(type(value) is bool or
                    isinstance(value, str) and value.lower() in
                    ("true", "false", "oui", "non"),
                    name + " : booléen requis")
            converted[name] = (value is True or isinstance(value, str) and
                               value.lower() in ("true", "oui"))
        elif type_name == "optional":
            require(isinstance(value, str), "Invalid optional field")
            if value.strip():
                converted[name] = value.strip()
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
    if kind == "event_state":
        return {"kind": "event_state", **values}
    return action(kind, **values)


def action_catalogue():
    """UI-readable fields; no Qt or game rules imported by the view."""
    return {kind: tuple(fields) for kind, fields in TACTICAL_FIELDS.items()}


# StoryBook effects execute after a REAL narrative choice, not on a tactical
# trigger. This distinction protects GameSession/Player replay semantics.
STORY_FIELDS = {
    "set_flag": (("flag", "Drapeau", "text"), ("value", "Valeur", "scalar")),
    "add_flag": (("flag", "Drapeau", "text"), ("amount", "Montant", "signed")),
    "grant_item": (("item", "ID équipement", "text"), ("quantity", "Quantité", "integer")),
    "gold": (("amount", "Variation or", "signed"),),
    "unlock_mission": (("mission", "Mission", "text"),),
    "recruit_hero": (("hero", "Héros", "text"),),
    "equip_hero": (("hero", "Héros", "text"), ("item", "Équipement", "text")),
}


def story_effect(kind, raw):
    """Build native StoryBook effect, validated further by GameProject."""
    require(kind in STORY_FIELDS and isinstance(raw, dict), "Unknown narrative effect")
    fields = STORY_FIELDS[kind]
    require(set(raw) == {name for name, _, _ in fields}, "Invalid narrative fields")
    payload = {"kind": kind}
    for key, _, type_name in fields:
        value = raw[key]
        if type_name in ("integer", "signed"):
            if isinstance(value, str):
                try:
                    parsed = int(value)
                except ValueError as exc:
                    raise RuleError("Expected integer for " + key) from exc
            else:
                require(type(value) is int, "Expected integer for " + key)
                parsed = value
            payload[key] = parsed
        elif type_name == "scalar":
            if isinstance(value, str):
                value = (True if value == "true" else
                         False if value == "false" else
                         int(value) if value.strip().lstrip("-").isdigit() else value)
            require(isinstance(value, (bool, int, str)), "Invalid flag scalar")
            payload[key] = value
        else:
            require(isinstance(value, str) and bool(value.strip()),
                    key + " is required")
            payload[key] = value.strip()
    return payload
