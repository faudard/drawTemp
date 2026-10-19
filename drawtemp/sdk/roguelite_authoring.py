"""R34.C — transactional opt-in authoring via existing AuthoringSession.

No sidecar truth: the recipe/library live in GameProject.extensions, so edits
participate in the canonical two-document validation, Undo/Redo and saves.
"""
from __future__ import annotations

from copy import deepcopy

from .authoring import AuthoringSession
from .simulation import thaw
from sporebound.model import Content, require
from sporebound.game_project import GameProject
from sporebound.roguelite import EXTENSION, validate_roguelite_spec


def preview_roguelite_project(session, recipe, library, *, biome, meta_reward=1):
    """Produce an unapplied AuthoringPlan; caller must explicitly apply it."""
    require(isinstance(session, AuthoringSession),
            "R34 authoring requires the canonical AuthoringSession")
    snapshot = session.snapshot()
    content = Content.from_dict(thaw(snapshot.content))
    project = GameProject.from_dict(thaw(snapshot.project), content)
    document = {
        "version": 1,
        "recipe": deepcopy(recipe.to_dict() if hasattr(recipe, "to_dict") else recipe),
        "library": deepcopy(library),
        "biome": biome,
        "meta_reward": meta_reward,
    }
    validate_roguelite_spec(document, content=content, project=project)

    def edit_project(data):
        updated = deepcopy(data)
        extensions = updated.setdefault("extensions", {})
        extensions[EXTENSION] = {
            "schema_version": 1, "data": deepcopy(document)}
        return updated

    return session.preview_project(edit_project, kind="r34-roguelite-project")
