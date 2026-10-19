"""R28.B — authoring adapter for R25's canonical versioned game_modes.

Headless and UI-independent: no second profile registry or file format.
Every edit is previewed and validated by the original R1 AuthoringSession.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.simulation import thaw
from sporebound.game_modes import FIELDS, PRESETS, VALUES, legacy_modes, resolve_scene_profile


class ProfileEditorError(ValueError):
    """User-facing scope/revision error; canonical validation remains authoritative."""


@dataclass(frozen=True)
class ProfilePreview:
    plan: object
    report: dict


def _pair(snapshot):
    return snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot


def profile_targets(snapshot):
    """Real IDs only, without creating a shadow scene catalogue."""
    data = _pair(snapshot)
    content, project = data["content"], data["project"]
    items = [(None, "Projet — profil par défaut")]
    seen = set()
    for mission in content["missions"]:
        key = mission["id"]
        if key not in seen:
            items.append((key, "Mission tactique : " + mission.get("name", key)))
            seen.add(key)
    for scene in project.get("story", {}).get("scenes", []):
        key = scene["id"]
        if key not in seen:
            items.append((key, "Scène narrative : " + scene.get("title", key)))
            seen.add(key)
    for key in project.get("exploration", {}):
        if key not in seen:
            items.append((key, "Exploration : " + key))
            seen.add(key)
    return tuple(items)


def inspect_profile(snapshot, scene_id=None):
    """Detached effective capabilities, explicit selection and source."""
    pair = _pair(snapshot)
    if scene_id not in dict(profile_targets(pair)):
        raise ProfileEditorError("Scène inconnue : " + repr(scene_id))
    manifest = pair["project"].get("game_modes") or {}
    declared = manifest or legacy_modes()
    if scene_id is None:
        entry = declared["default"]
        source = "legacy" if not manifest else "project"
    else:
        entry = declared["scenes"].get(scene_id)
        source = "scene" if entry is not None else "inherited"
    return {
        "scene_id": scene_id,
        "source": source,
        "selection": deepcopy(entry),
        "effective": resolve_scene_profile(manifest, scene_id),
        "revision": pair.get("revision", 0),
        "runtime_note": ("Profil déclaratif R25.A : les modes non tactiques "
                         "attendent l'intégration GameSession / Player R25–R28."),
    }


def preview_profile_edit(session: AuthoringSession, scene_id, entry,
                         *, expected_revision=None, protect_tactical=False):
    """Prepare ONE atomic undo operation on GameProject, never on Content.

    scene_id=None edits the default. entry=None restores inherited scope
    (or legacy SRPG default). Switching the default to a non-CT mode may
    opt-in to explicit CT pins for legacy missions, listed in report.
    """
    snap = session.snapshot()
    pair = snap.to_dict()
    if expected_revision is not None and snap.revision != expected_revision:
        raise ProfileEditorError("L'éditeur a changé : actualisez le profil.")
    if scene_id not in dict(profile_targets(pair)):
        raise ProfileEditorError("Scène inconnue : " + repr(scene_id))
    if entry is not None and type(entry) is not dict:
        raise ProfileEditorError("Choix attendu : preset ou profil typé.")
    if type(protect_tactical) is not bool:
        raise ProfileEditorError("Protection CT : booléen attendu.")
    original = pair["project"].get("game_modes") or {}
    before = original or legacy_modes()
    selected = deepcopy(entry)

    def transform(project):
        modes = deepcopy(project.get("game_modes") or legacy_modes())
        if scene_id is None:
            modes["default"] = selected if selected is not None else {"preset": "srpg"}
            if protect_tactical:
                # All legacy tactical missions are preserved in the same
                # transaction; report every newly pinned mission before apply.
                capabilities = resolve_scene_profile(modes)
                if capabilities["combat"] != "TACTICAL_CT":
                    for mission in pair["content"]["missions"]:
                        mid = mission["id"]
                        if mid not in modes["scenes"]:
                            modes["scenes"][mid] = deepcopy(before["default"])
        elif selected is None:
            modes["scenes"].pop(scene_id, None)
        else:
            modes["scenes"][scene_id] = selected
        # Do not change historical JSON merely by viewing or resetting a
        # legacy SRPG profile.
        if modes == legacy_modes():
            project.pop("game_modes", None)
        else:
            project["game_modes"] = modes
        return project

    plan = session.preview_project(transform, kind="r28.profile.update")
    after = thaw(plan.project).get("game_modes") or {}
    pinned = sorted(set(after.get("scenes", {})) -
                    set(before.get("scenes", {})) -
                    ({scene_id} if scene_id is not None else set()))
    report = {
        "source_revision": snap.revision,
        "scope": scene_id or "project",
        "before": inspect_profile(pair, scene_id),
        "after": {
            "manifest": deepcopy(after),
            "selection": deepcopy(
                (after or legacy_modes())["default" if scene_id is None else "scenes"].get(
                    scene_id) if scene_id is not None
                else (after or legacy_modes())["default"]
            ),
            "effective": resolve_scene_profile(after, scene_id),
        },
        "pinned_tactical_missions": pinned,
        "changed": original != after,
        "runtime_ready": resolve_scene_profile(after, scene_id)["combat"] == "TACTICAL_CT",
    }
    return ProfilePreview(plan, report)


def apply_profile_edit(session: AuthoringSession, preview: ProfilePreview):
    """R1 rejects stale/foreign plans and unchanged edits."""
    if not isinstance(preview, ProfilePreview):
        raise ProfileEditorError("Prévisualisation R28 invalide.")
    return session.apply(preview.plan)


__all__ = [
    "FIELDS", "VALUES", "PRESETS", "ProfileEditorError", "ProfilePreview",
    "profile_targets", "inspect_profile", "preview_profile_edit", "apply_profile_edit",
]
