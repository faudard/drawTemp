"""R9.C authoring bridge from tactical event IDs to GameProject cinematic cues.

A tactical action registry contains no sound/dialogue/camera operations. They
are authored as validated presentation timelines and consumed by the Player's
existing tactical_event hook, never silently accepted as inert trigger actions.
"""
from __future__ import annotations

from copy import deepcopy

from sporebound.cinematics import (cinematic_template, event_template,
                                    tactical_event_target)
from sporebound.model import require


PRESENTATION_FIELDS = {
    "dialogue": (("speaker", "Interlocuteur"), ("text", "Texte")),
    "sound": (("cue", "ID sonore"),),
    "actor": (("actor", "ID personnage"),),
    "camera": (),
    "background": (("color", "Couleur #RRGGBB"),),
    "fade": (("color", "Couleur #RRGGBB"),),
    "fx": (("effect", "Effet fire/smoke/rain/fog/light/camera_shake"),),
}


def presentation_cue(kind, cue_id, start_ms, duration_ms, fields):
    """Convert typed UI fields to an existing validated Cinematic event."""
    require(kind in PRESENTATION_FIELDS, "Unknown presentation cue")
    require(isinstance(fields, dict), "Invalid cue fields")
    require(set(fields) == {name for name, _ in PRESENTATION_FIELDS[kind]},
            "Unexpected presentation fields")
    require(type(start_ms) is int and start_ms >= 0 and
            type(duration_ms) is int and duration_ms > 0, "Invalid timing")
    row = event_template(kind, cue_id, start_ms, duration_ms)
    for name, value in fields.items():
        require(isinstance(value, str) and bool(value.strip()),
                "Le champ " + name + " doit être renseigné")
        row[name] = value.strip()
    return row


def add_event_cue(project, mission_id, event_id, *,
                  clip_id, clip_name, kind, cue_id,
                  start_ms=0, duration_ms=1000, fields=None):
    """Pure edit of the *existing* GameProject cinematic document.

    When the clip exists, it must already target this event. Otherwise a
    new clip is created at the same validated event hook. Both routes are
    persisted atomically by the caller's R1 AuthoringSession.
    """
    raw = deepcopy(project.to_dict())
    target = tactical_event_target(mission_id, event_id)
    clips = raw.setdefault("cinematics", [])
    found = next((clip for clip in clips if clip["id"] == clip_id), None)
    if found is None:
        require(isinstance(clip_name, str) and bool(clip_name.strip()),
                "Nom de cinématique requis")
        found = cinematic_template(clip_id, clip_name.strip(),
                                   "tactical_event", target)
        clips.append(found)
    else:
        require(found["trigger"] == {"kind": "tactical_event", "target": target},
                "Cette cinématique est liée à un autre événement")
    require(all(item["id"] != cue_id for item in found["events"]),
            "Cet identifiant de piste existe déjà")
    found["events"].append(presentation_cue(
        kind, cue_id, start_ms, duration_ms, fields or {}))
    return raw
