"""R41.B1 — canonical Party Studio authoring (headless, Qt-independent).

All project edits flow through the original R1 AuthoringSession's preview/apply
transaction. Runtime party state remains owned by the existing GameSession.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.classic_party import EXTENSION
from sporebound.game_modes import resolve_scene_profile
from sporebound.model import require


@dataclass(frozen=True)
class PartyDraft:
    plan: object
    before: dict | None
    after: dict
    campaign: str
    revision: int


def _pair(snapshot):
    return snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot


def party_campaigns(snapshot):
    project = _pair(snapshot)["project"]
    return tuple((row["id"], row["name"]) for row in project["campaigns"])


def party_heroes(snapshot):
    """Derive hero IDs from Content once; no R41 actor catalogue."""
    content = _pair(snapshot)["content"]
    roster = {}
    for mission in content["missions"]:
        for unit in mission["units"]:
            if unit["team"] == "player":
                roster.setdefault(unit["id"], unit.get("name") or unit["id"])
    return tuple(sorted(roster.items()))


def inspect_party(snapshot, campaign_id):
    pair = _pair(snapshot)
    project = pair["project"]
    require(campaign_id in dict(party_campaigns(pair)), "Unknown party campaign")
    extension = project.get("extensions", {}).get(EXTENSION, {})
    config = extension.get("data", {}).get("campaigns", {}).get(campaign_id)
    modes = project.get("game_modes") or {}
    rpg_scenes = [
        scene for scene in sorted({
            *project.get("exploration", {}),
            *(row["id"] for row in project.get("story", {}).get("scenes", [])),
        }) if resolve_scene_profile(modes, scene)["combat"] == "RPG_TURN"
    ]
    eligible = list(party_heroes(pair))
    return {
        "campaign": campaign_id,
        "revision": pair.get("revision", 0),
        "enabled": config is not None,
        "selection": deepcopy(config),
        "eligible": eligible,
        "rpg_scenes": rpg_scenes,
        "rpg_default": resolve_scene_profile(modes)["combat"] == "RPG_TURN",
    }


def preview_party_edit(session: AuthoringSession, campaign_id, *,
                       recruitable, initial, active, max_active,
                       expected_revision=None):
    """One validated authoring transaction; never touch saved or live GameSession."""
    snapshot = session.snapshot()
    before = inspect_party(snapshot, campaign_id)
    if expected_revision is not None:
        require(type(expected_revision) is int
                and expected_revision == snapshot.revision,
                "Party preview is stale; refresh the Studio session")
    require(before["rpg_default"] or before["rpg_scenes"],
            "Enable classic_rpg on project or exploration first (R28 profiles)")
    data = {"recruitable": list(recruitable), "initial": list(initial),
            "active": list(active), "max_active": max_active}

    def update(project):
        extensions = project.setdefault("extensions", {})
        entry = deepcopy(extensions.get(EXTENSION, {
            "schema_version": 1,
            "data": {"version": 1, "campaigns": {}},
        }))
        entry["data"]["campaigns"][campaign_id] = deepcopy(data)
        extensions[EXTENSION] = entry
        return project

    plan = session.preview_project(update, kind="r41.party.configure")
    return PartyDraft(plan, before["selection"], deepcopy(data),
                      campaign_id, snapshot.revision)


def apply_party_edit(session: AuthoringSession, draft: PartyDraft):
    require(isinstance(draft, PartyDraft), "Missing R41 party preview")
    return session.apply(draft.plan)


__all__ = ["PartyDraft", "party_campaigns", "party_heroes",
           "inspect_party", "preview_party_edit", "apply_party_edit"]
