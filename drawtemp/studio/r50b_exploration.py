"""R50.B routed exploration prototype using canonical R15/R1/R25 and Player slots.

This tests deterministic free movement followed by an authentic tactical CT
encounter. It is not real-time action COMBAT, a native Qt Player or a certified
action-adventure template.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from drawtemp.export.r15 import preflight
from drawtemp.export.templates import create_template
from drawtemp.sdk.authoring import AuthoringSession
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.player_controller import PlayerController
from sporebound.tactical_rpg3 import authored_rules_for_document


class ExplorationJourneyError(ValueError):
    pass


SCENE = "arrival"
TO_BATTLE = "to_arena"
BACK = "retreat"


def _configure(content: dict, project: dict) -> tuple[dict, dict]:
    """Edit the existing canonical GameProject, never introduce a parallel schema."""
    mission = content["missions"][0]
    mission_id = mission["id"]
    hero = next(unit for unit in mission["units"] if unit["team"] == "player")
    project["title"] = "La vallée du guet"
    project["subtitle"] = "Explorer, rejoindre une arène CT et revenir au village"
    project["story"]["entry_scenes"] = {}
    project["exploration"] = {
        SCENE: {
            "title": "Vallée du guet", "theme": "village",
            "width": 4, "height": 4, "start": [0, 1],
            "blocked": [[2, 1]],
            "interactions": [{
                "id": "exit", "title": "Chemin de garde",
                "text": "Un chemin mène aux remparts.", "pos": [1, 2],
                "required": False, "exit": True,
            }],
        },
    }
    project["game_modes"] = {
        "version": 1, "default": {"preset": "srpg"},
        "scenes": {
            SCENE: {"preset": "action"},
            mission_id: {"preset": "srpg"},
        },
    }
    project["scene_routes"] = {
        "version": 1, "start": SCENE,
        "links": [
            {"id": TO_BATTLE, "source": SCENE,
             "destination": mission_id, "spawn": list(hero["pos"])},
            {"id": BACK, "source": mission_id,
             "destination": SCENE, "spawn": [1, 1]},
        ],
    }
    return content, project


def author_exploration_prototype(destination: str | Path) -> Path:
    """Create a NEW R15 pair and prove edit→undo→redo→save under R1 validation.

    Call only inside the private R50.B staging directory. The publisher is
    responsible for destination no-overwrite and atomic final publication.
    """
    output = create_template("narrative", destination)
    content_path = output / "game.json"
    session = AuthoringSession.open(content_path)
    before = session.snapshot().to_dict()
    plan = session.preview_pair(_configure, kind="r50b.route-exploration")
    session.apply(plan)
    edited = session.snapshot().to_dict()
    if edited["project"] == before["project"]:
        raise ExplorationJourneyError("No exploration edit was applied")
    session.undo()
    restored = session.snapshot().to_dict()
    if (restored["content"], restored["project"]) != (
            before["content"], before["project"]):
        raise ExplorationJourneyError("Undo lost original authored state")
    session.redo()
    restored = session.snapshot().to_dict()
    if (restored["content"], restored["project"]) != (
            edited["content"], edited["project"]):
        raise ExplorationJourneyError("Redo lost authored exploration state")
    session.save()
    reopened = AuthoringSession.open(content_path).snapshot().to_dict()
    if (reopened["content"], reopened["project"]) != (
            edited["content"], edited["project"]):
        raise ExplorationJourneyError("Saved project differs from authored route")
    if reopened["dirty"]:
        raise ExplorationJourneyError("Reopened project has unsaved changes")
    if not preflight(content_path)["passed"]:
        raise ExplorationJourneyError("R15 preflight rejected routed exploration")
    return content_path


def check_exploration_player_journey(content_path: str | Path, profile: Path) -> dict:
    """Run the real PlayerController; exercise persisted free movement and CT.

    The isolated profile must be supplied by a temporary test/staging caller.
    No user slot is ever used. The resulting report is NOT release evidence.
    """
    path = Path(content_path)
    manifest = path.with_name(path.stem + ".game.json")
    before = (sha256(path.read_bytes()).hexdigest(),
              sha256(manifest.read_bytes()).hexdigest())
    checked = preflight(path)
    if not checked["passed"]:
        raise ExplorationJourneyError("R15 preflight failed: " + str(checked["errors"]))
    snapshot = AuthoringSession.open(path).snapshot().to_dict()
    raw = snapshot["content"]
    content = Content.from_dict(raw, rules=authored_rules_for_document(raw))
    project = GameProject.from_dict(snapshot["project"], content)
    if not project.scene_routes or project.scene_routes["start"] != SCENE:
        raise ExplorationJourneyError("Project has no expected R25 scene route")
    campaign = project.campaigns[0]["id"]
    player = PlayerController(content, project, profile)
    player.new_game(campaign, 1, seed=50)
    original = player.route_realtime_state()
    if original["scene"] != SCENE or original["tick"] != 0:
        raise ExplorationJourneyError("Player did not start in routed exploration")
    # A rejected input must not increment tick or mutate the Player slot.
    baseline = player.session.recording()
    try:
        player.route_realtime_step(2, 0)
    except RuleError:
        pass
    else:
        raise ExplorationJourneyError("Invalid free movement command was accepted")
    if player.session.recording() != baseline:
        raise ExplorationJourneyError("Invalid movement changed gameplay")
    for _ in range(8):
        last = player.route_realtime_step(1, 0)
    if last["tick"] != 8 or last["cell"] != [1, 1]:
        raise ExplorationJourneyError("Deterministic Player movement diverged")
    before_save = player.session.recording()
    reader = PlayerController(content, project, profile)
    reader.load_game(campaign, 1)
    if (reader.session.recording() != before_save or
            reader.route_realtime_state() != last):
        raise ExplorationJourneyError("Player free-movement resume diverged")
    moved_sha = before_save["digest"]
    tactical = reader.route_transition(TO_BATTLE)
    if (tactical["mode"] != "battle" or
            reader.session.active_battle is None):
        raise ExplorationJourneyError("Real CT encounter was not entered")
    battle_recording = reader.session.recording()
    resumed_battle = PlayerController(content, project, profile)
    resumed_battle.load_game(campaign, 1)
    if (resumed_battle.session.recording() != battle_recording or
            resumed_battle.session.active_battle is None):
        raise ExplorationJourneyError("Player CT resume diverged")
    resumed_battle.abandon_encounter()
    returned = resumed_battle.route_transition(BACK)
    if returned["scene"] != SCENE or returned["mode"] != "campaign":
        raise ExplorationJourneyError("Player return route failed")
    if resumed_battle.route_realtime_state()["cell"] != [1, 1]:
        raise ExplorationJourneyError("Return spawn is not persistent")
    final = resumed_battle.session.recording()
    resumed = PlayerController(content, project, profile)
    resumed.load_game(campaign, 1)
    if resumed.session.recording() != final:
        raise ExplorationJourneyError("Full routing journey replay diverged")
    if resumed.session.route_history != [TO_BATTLE, BACK]:
        raise ExplorationJourneyError("Route history was not preserved")
    after = (sha256(path.read_bytes()).hexdigest(),
             sha256(manifest.read_bytes()).hexdigest())
    if before != after:
        raise ExplorationJourneyError("Player mutated authored documents")
    return {
        "kind": "drawtemp-r50b-exploration-player",
        "schema": 1, "seed": 50, "ticks": 8,
        "fixed_movement": True, "rejected_invalid_intent": True,
        "realtime_save_resume": True, "ct_encounter_resume": True,
        "route_return_resume": True, "author_documents_unchanged": True,
        "movement_digest": moved_sha, "final_digest": final["digest"],
        "action_combat_verified": False, "qt_onscreen_verified": False,
        "native_player_verified": False, "release_9_0_certified": False,
    }
