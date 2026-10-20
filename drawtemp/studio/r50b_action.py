"""R50.B action-combat starter: R15/R1 authoring and replay-verified R26 Player.

This is one deliberately limited, original 4x4 headless action arena. Its
ActionRuntime remains a capability within the single GameSession save, not a
new game/project format. Action loot is NOT awarded to Campaign until R50.C.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from drawtemp.export.r15 import preflight
from drawtemp.export.templates import create_template
from drawtemp.sdk.authoring import AuthoringSession
from sporebound.action_scene_adapter import EXTENSION, authored_action_scene
from sporebound.action_runtime import ActionRuntime
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.player_controller import PlayerController
from sporebound.tactical_rpg3 import authored_rules_for_document


class ActionJourneyError(ValueError):
    pass


SCENE = "arrival"
ENEMY = "guard_wolf"


def _configure(content, project):
    """Apply only canonical R25 profile/router and validated extension fields."""
    mission = content["missions"][0]["id"]
    hero = next(u for u in content["missions"][0]["units"]
                if u["team"] == "player")
    project["title"] = "Le guet de la clairière"
    project["subtitle"] = "Un prototype de combat action déterministe"
    project["story"]["entry_scenes"] = {}
    project["exploration"] = {
        SCENE: {
            "title": "Clairière", "theme": "forest",
            "width": 4, "height": 4,
            "start": [0, 1], "blocked": [[2, 1]],
            "interactions": [{
                "id": "exit", "title": "Sentier",
                "text": "Sortie future vers le jeu tactique.",
                "pos": [1, 2], "required": False, "exit": True,
            }],
        },
    }
    project["game_modes"] = {
        "version": 1, "default": {"preset": "srpg"},
        "scenes": {SCENE: {"preset": "action"},
                   mission: {"preset": "srpg"}},
    }
    project["scene_routes"] = {
        "version": 1, "start": SCENE,
        "links": [
            {"id": "after_action_to_ct", "source": SCENE,
             "destination": mission, "spawn": list(hero["pos"])},
            {"id": "ct_to_action", "source": mission,
             "destination": SCENE, "spawn": [0, 1]},
        ],
    }
    project.setdefault("extensions", {})[EXTENSION] = {
        "schema_version": 1,
        "data": {
            "version": 1,
            "scenes": {
                SCENE: {
                    "id": SCENE, "width": 4, "height": 4,
                    "walls": [[2, 1]],
                    "hero": {"pos": [0, 1], "hp": 18},
                    "enemies": [{
                        "id": ENEMY, "pos": [1, 1], "hp": 2, "patrol": [],
                    }],
                    "objects": [],
                },
            },
        },
    }
    return content, project


def author_action_prototype(destination: str | Path) -> Path:
    """Build in an isolated directory, then R1 edit/undo/redo/save/reopen."""
    output = create_template("narrative", destination)
    path = output / "game.json"
    session = AuthoringSession.open(path)
    original = session.snapshot().to_dict()
    session.apply(session.preview_pair(_configure, kind="r50b.action-combat"))
    changed = session.snapshot().to_dict()
    if changed["project"] == original["project"]:
        raise ActionJourneyError("Action authoring did not change GameProject")
    session.undo()
    undone = session.snapshot().to_dict()
    if (undone["content"], undone["project"]) != (
            original["content"], original["project"]):
        raise ActionJourneyError("Undo lost original authoring state")
    session.redo()
    redone = session.snapshot().to_dict()
    if (redone["content"], redone["project"]) != (
            changed["content"], changed["project"]):
        raise ActionJourneyError("Redo lost R26 authored action scene")
    session.save()
    reopened = AuthoringSession.open(path).snapshot().to_dict()
    if reopened["dirty"] or (
            reopened["content"], reopened["project"]) != (
            changed["content"], changed["project"]):
        raise ActionJourneyError("Canonical action project did not roundtrip")
    if not preflight(path)["passed"]:
        raise ActionJourneyError("R15 refused action project preflight")
    return path


def check_action_player_journey(content_path: str | Path) -> dict:
    """Run two authentic R26 hits, checkpoint/reload mid-fight, verify replay.

    No native executable, Qt, hardware, visual Player or release rights
    are exercised. Temporary profile is private and removed on exit.
    """
    path = Path(content_path)
    manifest = path.with_name(path.stem + ".game.json")
    before = (sha256(path.read_bytes()).hexdigest(),
              sha256(manifest.read_bytes()).hexdigest())
    pre = preflight(path)
    if not pre["passed"]:
        raise ActionJourneyError("R15 preflight refused action game")
    pair = AuthoringSession.open(path).snapshot().to_dict()
    document = pair["content"]
    content = Content.from_dict(
        document, rules=authored_rules_for_document(document))
    project = GameProject.from_dict(pair["project"], content)
    scene = authored_action_scene(project, SCENE)
    campaign = project.campaigns[0]["id"]

    with TemporaryDirectory(prefix="drawtemp-r50b-action-") as temp:
        profile = Path(temp) / "profile.json"
        player = PlayerController(content, project, profile)
        player.new_game(campaign, 1, seed=50)
        fresh = player.route_action_state()
        if fresh["tick"] != 0 or fresh["scene"] != SCENE:
            raise ActionJourneyError("Player did not start in authored R26 scene")
        original_record = player.session.recording()
        try:
            player.route_action_step({"tick": 2, "attack": True})
        except RuleError:
            pass
        else:
            raise ActionJourneyError("Out-of-order action tick accepted")
        if player.session.recording() != original_record:
            raise ActionJourneyError("Rejected tick changed canonical gameplay")
        first = player.route_action_step(
            {"tick": 1, "dx": 1, "attack": True})
        if not any(e["kind"] == "enemy_hit" for e in first["events"]):
            raise ActionJourneyError("Real-time first hit did not register")
        first_record = player.session.recording()
        reader = PlayerController(content, project, profile)
        reader.load_game(campaign, 1)
        if reader.session.recording() != first_record or (
                reader.route_action_state() != first["state"]):
            raise ActionJourneyError("Mid-combat R26 save/resume mismatch")
        for tick in range(2, 13):
            reader.route_action_step({"tick": tick, "guard": True})
        second = reader.route_action_step({"tick": 13, "attack": True})
        if (second["state"]["enemies"][ENEMY]["hp"] != 0 or
                second["state"]["inventory"].get("coin") != 1):
            raise ActionJourneyError("Enemy defeat/reward replay diverged")
        recorded = reader.session.recording()
        saved_bytes = reader.path_for(campaign, 1).read_bytes()
        restored = PlayerController(content, project, profile)
        restored.load_game(campaign, 1)
        if (restored.session.recording() != recorded or
                restored.route_action_state() != second["state"]):
            raise ActionJourneyError("Final R26 Player checkpoint differs")
        if restored.path_for(campaign, 1).read_bytes() != saved_bytes:
            raise ActionJourneyError("Player silently rewrote combat checkpoint")
        if restored.session.progress.inventory.get("coin", 0):
            raise ActionJourneyError("Isolated R26 reward leaked into Campaign")
        validated = ActionRuntime.from_recording(
            recorded["scene_action"]["runtime"], expected_scene=scene)
        if validated.snapshot() != second["state"]:
            raise ActionJourneyError("Replay of authored R26 action differs")

    after = (sha256(path.read_bytes()).hexdigest(),
             sha256(manifest.read_bytes()).hexdigest())
    if before != after:
        raise ActionJourneyError("R26 Player mutated authored project")
    return {
        "kind": "drawtemp-r50b-action-player", "schema": 1,
        "authoring_pair_unchanged": True,
        "action_combat_attacks": 2, "action_combat_ticks": 13,
        "enemy_defeated": True, "reward_once_in_action_runtime": True,
        "player_save_resume": True, "same_gamesession_checkpoint": True,
        "replay_verified": True,
        "checkpoint_digest": recorded["digest"],
        "campaign_loot_integrated": False,
        "qt_onscreen_verified": False, "native_player_verified": False,
        "release_9_0_certified": False,
    }
