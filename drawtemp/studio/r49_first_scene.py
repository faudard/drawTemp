"""R49.C2: canonical first-scene + first-action authoring in one R1 edit.

Uses existing R9 event_composer and StoryBook authoring; no custom gameplay
schema, runtime interpreter, shadow file or implicit overwrite.
"""
from __future__ import annotations

from dataclasses import dataclass
from re import fullmatch

from drawtemp.sdk.authoring import AuthoringSession
from sporebound import event_composer, story_authoring
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.tactical_rpg3 import authored_rules_for_document


class FirstSceneError(ValueError):
    """Creator-facing validation failure: the live session remains unchanged."""


@dataclass(frozen=True)
class FirstSceneRequest:
    mission_id: str
    event_id: str
    scene_id: str
    title: str
    speaker: str
    dialogue: str
    action_message: str
    tick: int = 1


def validate_first_scene(snapshot, request: FirstSceneRequest):
    """Validate inputs and target identity against a canonical R1 snapshot.

    A scene and a trigger must not be silently overwritten. Only tactical CT
    message actions are offered by this starter flow; this is not an action
    adventure/RPG/hybrid authoring or a realtime trigger engine.
    """
    if not isinstance(request, FirstSceneRequest):
        raise FirstSceneError("Entrée de scénario invalide")
    for label, value in (
        ("Mission", request.mission_id), ("ID événement", request.event_id),
        ("ID scène", request.scene_id),
    ):
        if not isinstance(value, str) or not fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", value):
            raise FirstSceneError(label + " : identifiant attendu (lettres, chiffres, _)")
    for label, value, limit in (
        ("Titre", request.title, 120),
        ("Intervenant", request.speaker, 120),
        ("Dialogue", request.dialogue, 2000),
        ("Action message", request.action_message, 1000),
    ):
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise FirstSceneError(label + " : texte requis (1.." + str(limit) + ")")
    if type(request.tick) is not int or not 1 <= request.tick <= 100000:
        raise FirstSceneError("Déclenchement : tick entre 1 et 100000")
    data = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
    missions = [row for row in data["content"]["missions"]
                if row["id"] == request.mission_id]
    if len(missions) != 1:
        raise FirstSceneError("Mission introuvable")
    if any(row["id"] == request.event_id for row in missions[0].get("triggers", [])):
        raise FirstSceneError("L'ID événement existe déjà : aucun remplacement")
    if any(row["id"] == request.scene_id for row in
           data["project"].get("story", {}).get("scenes", [])):
        raise FirstSceneError("L'ID scène existe déjà : aucun remplacement")
    return request


def preview_first_scene(session: AuthoringSession, request: FirstSceneRequest, *,
                        expected_revision=None):
    """Return one detached R1 plan; never commit during preview."""
    if not isinstance(session, AuthoringSession):
        raise TypeError("AuthoringSession attendu")
    current = session.snapshot()
    if expected_revision is not None and current.revision != expected_revision:
        raise FirstSceneError("Vue obsolète : actualiser avant d'appliquer")
    validate_first_scene(current, request)

    def edit(content, project):
        # Recheck after preview because a transaction can become stale.
        validate_first_scene({"content": content, "project": project}, request)
        condition = event_composer.condition("tick", tick=request.tick)
        message = event_composer.action("message", text=request.action_message)
        authored_content = event_composer.save_event(
            content, request.mission_id, request.event_id, condition, [message])
        checked_content = Content.from_dict(
            authored_content, rules=authored_rules_for_document(authored_content))
        checked_project = GameProject.from_dict(project, checked_content)
        with_scene = story_authoring.create_scene(
            checked_project, checked_content,
            request.scene_id, request.title.strip(), request.dialogue.strip(),
            speaker=request.speaker.strip())
        linked = story_authoring.set_tactical_scene(
            with_scene, checked_content,
            request.mission_id, request.event_id, request.scene_id)
        return authored_content, linked.to_dict()

    return session.preview_pair(
        edit, kind="r49.creator.first-scene", mission_id=request.mission_id,
        views=("workspace", "inspector", "renderer", "minimap"))


def apply_first_scene(session: AuthoringSession, request: FirstSceneRequest, *,
                      expected_revision=None):
    """One commit and one Undo step for scene, trigger, action and link."""
    return session.apply(preview_first_scene(
        session, request, expected_revision=expected_revision))
