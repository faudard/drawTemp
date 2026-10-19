"""R35.C1: transactional living-world authoring over the existing R1 history.

The source of truth is GameProject.extensions, not an editor-side NPC table.
"""
from copy import deepcopy
from dataclasses import dataclass

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.living_world import EXTENSION


@dataclass(frozen=True)
class LivingWorldPreview:
    plan: object
    report: dict


def preview_living_world(session: AuthoringSession, document,
                         *, expected_revision=None):
    """Preview replacing the complete R35 document in one undoable operation.

    `document=None` removes only the living-world extension. Validation of
    actors/scenes/shops happens through the existing AuthoringSession pair.
    """
    if not isinstance(session, AuthoringSession):
        raise TypeError("Expected the active AuthoringSession")
    snap = session.snapshot()
    if expected_revision is not None and expected_revision != snap.revision:
        raise ValueError("Outdated living-world editor revision")
    if document is not None and type(document) is not dict:
        raise ValueError("Living-world document must be an object or None")
    before = snap.to_dict()["project"].get("extensions", {}).get(EXTENSION)
    proposed = deepcopy(document)

    def edit(project):
        extensions = project.setdefault("extensions", {})
        if proposed is None:
            extensions.pop(EXTENSION, None)
        else:
            extensions[EXTENSION] = {
                "schema_version": 1, "data": deepcopy(proposed),
                "references": []}
        return project

    plan = session.preview_project(edit, kind="r35.living-world.author")
    return LivingWorldPreview(plan, {
        "source_revision": snap.revision,
        "before_enabled": before is not None,
        "after_enabled": proposed is not None,
        "npc_count": len(proposed.get("npcs", [])) if proposed else 0,
        "shop_count": len(proposed.get("shops", [])) if proposed else 0,
        "quest_count": len(proposed.get("daily_quests", [])) if proposed else 0,
    })


def apply_living_world(session: AuthoringSession, preview: LivingWorldPreview):
    if not isinstance(preview, LivingWorldPreview):
        raise TypeError("Expected a validated R35 preview")
    return session.apply(preview.plan)
