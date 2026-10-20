"""R74.C1: three atomic, editable R27 physical dungeon missions from R74 seeds.

The R34 room graphs are used as vetted inspirations, NOT instantiated with
1:1 room/edge parity. This generator creates one locked R27 room per proposal,
with an actual key, a goal beyond the door, and a bounded R27 symbolic witness.
No second map format, no disk mutation, and no gameplay/GPU/export certificate.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import re

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.studio.dungeon_authoring import DungeonStudio
from drawtemp.studio.map_authoring import MapStudio
from .r74_assisted_dungeons import (
    AssistedDungeonController, DungeonAssistError, DungeonSuggestion,
)


_PREFIX = re.compile(r"[a-z][a-z0-9_]{0,11}\Z")


@dataclass(frozen=True)
class PhysicalDungeonPreview:
    """An unapplied R1 plan, with detached R27 puzzle evidence."""

    revision: int
    prefix: str
    proposal_seeds: tuple[int, ...]
    mission_ids: tuple[str, ...]
    campaign_id: str
    proofs: tuple[dict, ...]
    plan: object
    controller: object

    def to_dict(self):
        return {
            "revision": self.revision, "prefix": self.prefix,
            "proposal_seeds": list(self.proposal_seeds),
            "missions": list(self.mission_ids),
            "campaign": self.campaign_id,
            "proofs": deepcopy(self.proofs),
            "applied": False, "physical_puzzle_witness": True,
            "r34_graph_parity": False, "combat_ai_certified": False,
            "player_save_certified": False, "player_export_certified": False,
        }


def _proof(dungeon: DungeonStudio, *, mission_id: str, key_id: str,
           door_id: str, destination):
    """R27 state-space proof is narrower than real tactical AI playthrough."""
    report = dungeon.puzzle_debug(state_budget=50000)
    witness = tuple(report.get("witness", ()))
    allowed_warnings = {"Enemy AI and combat are not modeled"}
    if (report["unreachable_goals"] or
            list(destination) not in report["reachable_goals"] or
            not witness or not witness[0] == "spawn" or
            "collect " + key_id not in witness or
            "open " + door_id not in witness or
            any(w not in allowed_warnings for w in report.get("warnings", ())) or
            report["states"] >= 50000):
        raise DungeonAssistError(
            "physical_route_unproven",
            f"{mission_id}: no bounded physical key→door→goal witness")
    return {
        "mission": mission_id,
        "goal": list(destination),
        "key": key_id,
        "door": door_id,
        "states": report["states"],
        "witness": list(witness),
        "warnings": list(report["warnings"]),
        "scope": "R27 single-hero movement and key/door puzzle; excludes enemy AI",
    }


def prepare_physical_dungeons(
    controller: AssistedDungeonController, proposals, *, prefix="r74"
) -> PhysicalDungeonPreview:
    """Dry run three real mission edits, then return one unapplied R1 plan.

    All three inputs must be the controller's current, verified R74 proposals.
    The original editor's Content and GameProject stay unchanged, even on
    failure. Every mission uses R27's canonical editors and puzzle debugger.
    """
    if not isinstance(controller, AssistedDungeonController):
        raise DungeonAssistError("invalid_controller", "Use R74 assistant")
    if (type(prefix) is not str or _PREFIX.fullmatch(prefix) is None):
        raise DungeonAssistError("invalid_prefix", "Use 1..12 safe lowercase ID")
    if type(proposals) not in (tuple, list) or len(proposals) != 3:
        raise DungeonAssistError("invalid_count", "Exactly three R74 proposals required")
    if len({id(item) for item in proposals}) != 3:
        raise DungeonAssistError("duplicate_suggestion", "Use three distinct proposals")
    if len({item.topology_digest for item in proposals
            if isinstance(item, DungeonSuggestion)}) != 3:
        raise DungeonAssistError("duplicate_suggestion", "Distinct topologies required")
    for proposal in proposals:
        # Includes proposal identity, full payload signature, R34 reproduction,
        # active editor revision and rights checks. No mutation occurs.
        controller.prepare_selection(proposal)

    original = controller.session.snapshot().to_dict()
    ids = tuple(f"{prefix}_dungeon_{i}" for i in range(1, 4))
    campaign_id = prefix + "_trilogy"
    existing = {mission["id"] for mission in original["content"]["missions"]}
    if set(ids) & existing:
        raise DungeonAssistError("duplicate_mission", "Generated mission IDs already exist")
    if any(c["id"] == campaign_id for c in original["project"]["campaigns"]):
        raise DungeonAssistError("duplicate_campaign", "Generated campaign already exists")
    sandbox = MapStudio(AuthoringSession.new(
        original["content"], original["project"]))
    dungeon = DungeonStudio(sandbox)
    evidence = []
    for index, proposal in enumerate(proposals):
        mid = ids[index]
        # Three distinct, seed-order-stable footprints; 16x16 is a supported
        # R5 board. All doors are aligned to the accessible upper wall.
        door_x = (5, 7, 9)[index]
        name = ("Les Archives", "La Galerie", "Le Sanctuaire")[index]
        origin = ids[index - 1] if index else None
        dungeon.create_dungeon(mid, name, width=16, height=16, from_map=origin)
        dungeon.build_room((3, 3), (12, 12), entrance=(door_x, 3))
        key_id = f"{prefix}_key_{index + 1}"
        dungeon.place_puzzle(key_id, "key", (door_x, 2), door_id="room_door")
        goal = (door_x, 8)
        sandbox.set_objective("extract")
        sandbox.paint([goal], "goal")
        proof = _proof(dungeon, mission_id=mid, key_id=key_id,
                       door_id="room_door", destination=goal)
        proof["source_seed"] = proposal.seed
        proof["source_topology_digest"] = proposal.topology_digest
        proof["mission_digest"] = sha256(
            json.dumps(sandbox.mission(), sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True).encode("utf-8")
        ).hexdigest()
        evidence.append(proof)

    # The R27/R1 schema already owns campaigns; don't introduce a sidecar.
    def add_campaign(data):
        updated = deepcopy(data)
        updated["campaigns"].append({
            "id": campaign_id,
            "name": "Trois donjons assistés R74",
            "description": "Énigmes physiques avec clés et portes, vérifiées R27",
            "start_mission": ids[0],
        })
        return updated
    sandbox.authoring.apply(sandbox.authoring.preview_project(
        add_campaign, kind="r74-physical-campaign"))
    detached = sandbox.snapshot()
    plan = controller.session.preview_pair(
        lambda _content, _project: (
            deepcopy(detached["content"]), deepcopy(detached["project"])),
        kind="r74-physical-three-dungeons",
    )
    return PhysicalDungeonPreview(
        revision=original["revision"], prefix=prefix,
        proposal_seeds=tuple(p.seed for p in proposals),
        mission_ids=ids, campaign_id=campaign_id,
        proofs=tuple(deepcopy(evidence)), plan=plan, controller=controller,
    )


def apply_physical_dungeons(controller: AssistedDungeonController,
                            preview: PhysicalDungeonPreview):
    """Explicit selection: one canonical validated edit, one shared Undo."""
    if (not isinstance(preview, PhysicalDungeonPreview)
            or preview.controller is not controller):
        raise DungeonAssistError("foreign_preview", "Preview belongs to another editor")
    if controller.session.revision != preview.revision:
        raise AuthoringError(
            "stale_revision", "r74-physical-apply",
            "The authoring project changed since the physical preview")
    # AuthoringSession.apply enforces the owning lease, revalidates both
    # documents and records exactly one transaction.
    transition = controller.session.apply(preview.plan)
    controller.invalidate()
    return transition
