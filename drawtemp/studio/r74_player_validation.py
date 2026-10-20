"""R74.C3: bounded tactical Player evidence for physical R74.C2 dungeon trilogy.

The gate uses canonical Content/GameProject, real GameSession commands and
R27 physical witnesses. It never changes the author's session or claims
native binary certification. It fails closed on unsupported encounter budgets,
unplayable tactical paths, unverified export preflight or missing runtime.
"""
from __future__ import annotations

from ast import literal_eval
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from drawtemp.core import Content, GameProject, RuleError
from drawtemp.export.r15 import preflight
from drawtemp.sdk.authoring import AuthoringSession, AuthoringError
from drawtemp.sdk.simulation import thaw
from sporebound.game_session import GameSession
from sporebound.tactical_rpg3 import authored_rules_for_document

from .r74_assisted_dungeons import AssistedDungeonController, DungeonAssistError
from .r74_spatial_dungeons import (
    SpatialDungeonPreview, _digest, prepare_spatial_dungeons,
)

MAX_PLAYER_ENCOUNTERS = 6
MAX_PER_ROOM = 2
MAX_PLAYER_COMMANDS = 1800
MAX_ENEMY_ACTIVATIONS = 200


def _models(plan):
    raw = thaw(plan.content)
    manifest = thaw(plan.project)
    content = Content.from_dict(raw, rules=authored_rules_for_document(raw))
    project = GameProject.from_dict(manifest, content)
    return raw, manifest, content, project


def _place_encounters(raw, mission_ids, proposals, proofs):
    """Add exactly R34's bounded encounter counts as REAL tactical enemies.

    The single default R27 enemy is replaced, never counted as an invisible
    extra. No zero-enemy mission can be called release-ready (R1 requires one).
    Each encounter stays away from center/key/chest and corridor thresholds.
    """
    missions = {m["id"]: m for m in raw["missions"]}
    reports = []
    for mid, suggestion, proof in zip(mission_ids, proposals, proofs):
        mission = missions[mid]
        planned = suggestion.layout["rooms"]
        amount = sum(r["encounters"] for r in planned)
        if not 1 <= amount <= MAX_PLAYER_ENCOUNTERS:
            raise DungeonAssistError(
                "encounter_limit", f"{mid}: requires 1..{MAX_PLAYER_ENCOUNTERS} encounters")
        if any(r["encounters"] > MAX_PER_ROOM for r in planned):
            raise DungeonAssistError(
                "encounter_limit", f"{mid}: maximum {MAX_PER_ROOM} per room")
        prototype = next((u for u in mission["units"] if u["team"] == "enemy"), None)
        if prototype is None:
            raise DungeonAssistError("missing_enemy", "R27 mission has no enemy template")
        heroes = [u for u in mission["units"] if u["team"] == "player"]
        taken = {tuple(u["pos"]) for u in heroes}
        taken |= {tuple(o["pos"]) for o in mission["objects"]}
        taken |= {tuple(mission["goal"][0])}
        enemies, assignments = [], []
        for room in planned:
            center = proof["room_centers"][str(room["id"])]
            x, y = center
            # Orthogonal spacing prevents overlap with authored key/goal,
            # chest and corridors; all offsets lie INSIDE the 5x5 room.
            candidates = [
                (x + 1, y + 1), (x - 1, y - 1),
                (x + 1, y - 1), (x - 1, y + 1),
                (x + 1, y), (x - 1, y),
            ]
            for index in range(room["encounters"]):
                cell = next((p for p in candidates if p not in taken), None)
                if cell is None:
                    raise DungeonAssistError(
                        "encounter_overlap", f"{mid}: no legal enemy spawn in room {room['id']}")
                enemy = deepcopy(prototype)
                enemy["id"] = f"r74_enemy_{room['id']}_{index}"
                enemy["name"] = f"Gardien salle {room['id']} · {index + 1}"
                enemy["pos"] = list(cell)
                enemy["speed"] = 1
                enemies.append(enemy)
                taken.add(cell)
                assignments.append({"room": room["id"], "pos": list(cell)})
        mission["units"] = heroes + enemies
        # Chest value is 25 gold per R34 loot unit; assert, do not assume,
        # all allocated rooms have a real chest with exactly this amount.
        expected_loot = {
            int(room["id"]): room["loot"]
            for room in planned if room["loot"] > 0}
        chests = {
            int(obj["id"].split("_")[-1]): obj
            for obj in mission["objects"] if obj["kind"] == "chest"
            and obj["id"].startswith("r74_chest_")
        }
        if set(chests) != set(expected_loot) or any(
                chests[rid]["amount"] != count * 25
                for rid, count in expected_loot.items()):
            raise DungeonAssistError(
                "loot_parity", f"{mid}: numeric R34 loot not faithfully materialized")
        reports.append({
            "mission": mid, "source_seed": suggestion.seed,
            "encounter_budget": amount, "spawned_enemies": len(enemies),
            "spawn_assignments": assignments,
            "loot_units": sum(expected_loot.values()),
            "real_chest_value": sum(c["amount"] for c in chests.values()),
            "gold_per_loot_unit": 25,
        })
    return reports


def _action_tokens(proof):
    witness = proof["exit_witness"]["witness"]
    if not witness or witness[0] != "spawn":
        raise DungeonAssistError("player_witness", "Missing R27 source witness")
    actions = []
    for row in witness[1:]:
        if row.startswith("walk "):
            value = literal_eval(row[5:])
            if (type(value) is not tuple or len(value) != 2
                    or any(type(v) is not int for v in value)):
                raise DungeonAssistError("player_witness", "Malformed witness step")
            actions.append(("walk", tuple(value)))
        elif row.startswith("collect "):
            actions.append(("interact", row[8:]))
        elif row.startswith("open "):
            actions.append(("interact", row[5:]))
        else:
            raise DungeonAssistError("player_witness", "Unsupported witness action: " + row)
    return actions


def _next_hero(session, stats):
    """Advance real CT scheduler without injecting an impossible activation."""
    for _ in range(MAX_ENEMY_ACTIVATIONS + MAX_PLAYER_COMMANDS):
        if session.finalized:
            return None
        active = session.battle.active
        if active is not None:
            if active.team == "player":
                return active
            stats["enemy_activations"] += 1
            if stats["enemy_activations"] > MAX_ENEMY_ACTIVATIONS:
                raise DungeonAssistError("player_budget", "Too many enemy activations")
            session.ai_turn()
        else:
            # Battle begins with an active actor in the canonical rules. An
            # absent actor during unresolved combat is an engine failure.
            raise DungeonAssistError("player_no_actor", "Tactical scheduler has no actor")
    raise DungeonAssistError("player_budget", "Could not obtain player activation")


def _finish_turn(session, stats):
    session.execute({"kind": "end"})
    stats["commands"] += 1
    if stats["commands"] > MAX_PLAYER_COMMANDS:
        raise DungeonAssistError("player_budget", "Maximum player commands reached")
    return _next_hero(session, stats)


def _follow_mission(session, proof):
    """Translate R27 four-way witness into legal bounded tactical actions.

    Choose only the farthest contiguous witness cell currently reachable by
    the ACTUAL moving hero; never teleport or spoof a mission result.
    """
    actions = _action_tokens(proof)
    stats = {"mission": proof["mission"], "commands": 0,
             "enemy_activations": 0, "interactions": [], "moves": 0}
    actor = _next_hero(session, stats)
    index = 0
    while index < len(actions):
        if session.finalized:
            break
        if actor is None:
            raise DungeonAssistError("player_defeat", "Battle finalized before exit")
        if stats["commands"] >= MAX_PLAYER_COMMANDS:
            raise DungeonAssistError("player_budget", "Player command budget exceeded")
        kind, target = actions[index]
        if kind == "interact":
            if actor.acted:
                actor = _finish_turn(session, stats)
                continue
            session.execute({"kind": "interact", "object": target})
            stats["commands"] += 1
            stats["interactions"].append(target)
            index += 1
            actor = session.battle.active if not session.finalized else None
            continue
        if tuple(actor.pos) == target:
            # The R27 symbolic witness may list a position already reached
            # by a longer but legal tactical move on the previous activation.
            index += 1
            continue
        if actor.moved:
            actor = _finish_turn(session, stats)
            continue
        reachable = session.battle.reachable(actor)
        # Follow only the contiguous cells leading up to the next semantic
        # interaction. Tactical movement respects walls and blocking actors.
        farthest = -1
        j = index
        while j < len(actions) and actions[j][0] == "walk":
            if actions[j][1] in reachable:
                farthest = j
            j += 1
        if farthest < index:
            # A cell in the R27 path might be occupied by a moving enemy.
            # Fail explicitly rather than sidestep and claim this witness
            # represents an actual Player walkthrough.
            raise DungeonAssistError(
                "player_path_blocked",
                f"{proof['mission']}: next witness cell {target} unreachable")
        position = actions[farthest][1]
        if tuple(actor.pos) != position:
            session.execute({"kind": "move", "cell": list(position)})
            stats["commands"] += 1
            stats["moves"] += 1
        index = farthest + 1
        actor = session.battle.active if not session.finalized else None

    if not session.finalized or session.battle.result != "victory":
        raise DungeonAssistError(
            "player_incomplete", proof["mission"] + ": goal did not settle victory")
    stats["result"] = session.battle.result
    stats["complete"] = True
    return stats


def verify_trilogy_player(content, project, campaign_id, proofs, *, seed=74):
    """Actual three-mission GameSession actions, gates and checkpoint replay."""
    if len(proofs) != 3:
        raise DungeonAssistError("player_scope", "Three R74 missions required")
    session = GameSession.new(content, project, campaign_id, seed=seed)
    reports = []
    for index, proof in enumerate(proofs):
        mid = proof["mission"]
        if mid not in session.available_missions():
            raise DungeonAssistError("player_campaign_gate", mid + " unavailable")
        session.start_mission(mid)
        stage = _follow_mission(session, proof)
        session.return_to_campaign()
        # Verify BOTH portable in-memory canonical replay and a real, scoped
        # disk checkpoint after each victory. Temporary files are cleaned
        # before returning to the caller; this never saves the editor project.
        snapshot = session.recording()
        check = GameSession.from_recording(snapshot, content, project)
        if check.recording() != snapshot:
            raise DungeonAssistError("player_replay", mid + " in-memory replay diverged")
        with TemporaryDirectory(prefix="r74-stage-save-") as folder:
            checkpoint = Path(folder) / "game-session.json"
            session.save(checkpoint)
            restored = GameSession.load(checkpoint, content, project)
            if restored.recording() != snapshot:
                raise DungeonAssistError("player_replay", mid + " saved checkpoint diverged")
            session = restored
        stage["recording_digest"] = _digest(snapshot)
        stage["checkpoint_disk_roundtrip"] = True
        stage["completed"] = mid in session.progress.completed
        if not stage["completed"]:
            raise DungeonAssistError("player_progress", mid + " not marked completed")
        reports.append(stage)
    return {
        "campaign": campaign_id, "stages": reports,
        "completed": True,
        "gold": session.progress.gold,
        "final_recording_digest": _digest(session.recording()),
        "scope": "actual headless tactical GameSession; not Qt/manual GPU",
    }


@dataclass(frozen=True)
class R74PlayerCandidate:
    revision: int
    prefix: str
    missions: tuple[str, ...]
    campaign_id: str
    spatial: SpatialDungeonPreview
    encounter_reports: tuple[dict, ...]
    gameplay: dict
    export_preflight: dict
    plan: object
    controller: object
    signature: str

    def to_dict(self):
        return {
            "revision": self.revision, "prefix": self.prefix,
            "missions": list(self.missions), "campaign": self.campaign_id,
            "encounters": deepcopy(self.encounter_reports),
            "gameplay": deepcopy(self.gameplay),
            "export_preflight": deepcopy(self.export_preflight),
            "signature": self.signature,
            "applied": False, "headless_player_verified": True,
            "native_player_export_certified": False,
            "qt_gpu_certified": False,
        }


def _signed(candidate):
    return _digest({
        "revision": candidate.revision, "prefix": candidate.prefix,
        "missions": candidate.missions, "campaign": candidate.campaign_id,
        "encounters": candidate.encounter_reports,
        "gameplay": candidate.gameplay,
        "export_preflight": candidate.export_preflight,
        "spatial_digest": candidate.spatial.evidence_digest,
        "spatial_report_digest": _digest(candidate.spatial.to_dict()),
        "canonical_content_digest": _digest(thaw(candidate.plan.content)),
        "canonical_project_digest": _digest(thaw(candidate.plan.project)),
    })


def prepare_r74_player_candidate(controller: AssistedDungeonController, proposals,
                                 *, prefix="r74p") -> R74PlayerCandidate:
    """Simulate and preflight in disposable space. No live project edit."""
    spatial = prepare_spatial_dungeons(controller, proposals, prefix=prefix)
    raw, manifest, _, _ = _models(spatial.plan)
    encounters = _place_encounters(raw, spatial.mission_ids, proposals, spatial.proofs)
    # A NEW validated editor history constructs the finalized two documents.
    candidate = AuthoringSession.new(raw, manifest)
    content, project = Content.from_dict(
        candidate.snapshot().to_dict()["content"],
        rules=authored_rules_for_document(candidate.snapshot().to_dict()["content"])
    ), None
    project = GameProject.from_dict(candidate.snapshot().to_dict()["project"], content)
    gameplay = verify_trilogy_player(
        content, project, spatial.campaign_id, spatial.proofs)
    with TemporaryDirectory(prefix="drawtemp-r74-gate-") as folder:
        path = Path(folder) / "r74.json"
        candidate.save_as(path)
        report = preflight(path, require_licenses=True)
    if not report["passed"] or report["errors"]:
        raise DungeonAssistError(
            "export_preflight", "R15 strict rights/content preflight failed: " +
            "; ".join(report["errors"]))
    concise = {
        "passed": True, "rights_attestations_checked": report["rights_attestations_checked"],
        "warnings": list(report["warnings"]),
        "missions_checked": list(spatial.mission_ids),
        "native_runtime_included": False,
    }
    payload = candidate.snapshot().to_dict()
    plan = controller.session.preview_pair(
        lambda _c, _p: (deepcopy(payload["content"]), deepcopy(payload["project"])),
        kind="r74-player-trilogy",
    )
    result = R74PlayerCandidate(
        revision=spatial.revision, prefix=prefix, missions=spatial.mission_ids,
        campaign_id=spatial.campaign_id, spatial=spatial,
        encounter_reports=tuple(deepcopy(encounters)), gameplay=deepcopy(gameplay),
        export_preflight=concise, plan=plan, controller=controller, signature="",
    )
    from dataclasses import replace
    return replace(result, signature=_signed(result))


def apply_r74_player_candidate(controller: AssistedDungeonController,
                               candidate: R74PlayerCandidate):
    if not isinstance(candidate, R74PlayerCandidate) or candidate.controller is not controller:
        raise DungeonAssistError("foreign_preview", "Not the original editor candidate")
    if candidate.signature != _signed(candidate):
        raise DungeonAssistError("modified_preview", "Evidence modified since preview")
    if controller.session.revision != candidate.revision:
        raise AuthoringError(
            "stale_revision", "r74-player-apply", "Editor revision changed")
    result = controller.session.apply(candidate.plan)
    controller.invalidate()
    return result
