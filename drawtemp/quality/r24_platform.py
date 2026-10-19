"""R24.D — software acceptance gate for a genuinely independent second game.

Run the production Content/GameProject, AuthoringSession, Simulation and
R1 replay certification. Deliberately do not certify GPU, art rights or a
native clean-machine Player solely from unit tests.
"""
from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from importlib.resources import files
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from drawtemp.core import Content, GameProject
from drawtemp.export.r15 import preflight
from drawtemp.sdk import AuthoringSession, Simulation, certify_trace, negotiate_sdk
from drawtemp.sdk.replay import ReplayCommand, verify_sequence
from sporebound.studio_transaction import validate_pair


class PlatformGateError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


R24_SECOND_GAME = "asterion"
R24_CAMPAIGN = "main"
R24_FIRST_MISSION = "signal_depot"
R24_TRACE = (
    ReplayCommand("choose_story_option", ("launch",)),
    ReplayCommand("start_mission", (R24_FIRST_MISSION,)),
    ReplayCommand("execute", ({"kind": "end", "facing": [0, 1]},)),
)
DEFAULT_SEEDS = (1, 17, 221)
MANUAL_RELEASE_REQUIREMENTS = (
    "R23 stable and all R24 P1 gates merged/validated on final master SHA",
    "Native Qt Player built, exported and run on clean Windows/Linux/macOS machines",
    "Actual renderer equivalence and onscreen GPU/frame-time measurements approved",
    "Legally verified art provenance, modification and redistribution rights",
    "Both missions completed through a genuine Player walkthrough, with creator UX and signed release evidence",
)


def _sha(obj):
    return sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode("utf-8")).hexdigest()


def source_paths():
    root = files("drawtemp").joinpath("creator_examples")
    return root.joinpath("asterion.json"), root.joinpath("asterion.game.json")


def _content_project(path=None):
    content_path, project_path = source_paths() if path is None else (
        Path(path), Path(path).with_name(Path(path).stem + ".game.json"))
    content = Content.from_dict(json.loads(content_path.read_text(encoding="utf-8")))
    project = GameProject.from_dict(
        json.loads(project_path.read_text(encoding="utf-8")), content)
    return content, project


def second_game_software_report(*, content_path=None, seeds=DEFAULT_SEEDS):
    """Certify software traces and round trips; never manufacture release success.

    Raises an explicit failure on invalid inputs or divergent state. The
    returned report always keeps native/distribution/visual gates OPEN.
    """
    seeds = tuple(seeds)
    if not seeds or len(seeds) > 8 or any(
            type(seed) is not int or not 0 <= seed <= 2147483647 for seed in seeds
    ) or len(seeds) != len(set(seeds)):
        raise PlatformGateError("invalid_seeds", "Choose 1..8 unique nonnegative seed values")
    try:
        negotiate_sdk((1, 0), required_features=(
            "simulation.v1", "authoring.v1", "certification.v1",
            "project-extensions.v1"))
        content, project = _content_project(content_path)
        document, manifest = validate_pair(content.to_dict(), project.to_dict())
        if not all(m in content.missions for m in ("signal_depot", "reactor_vault")):
            raise PlatformGateError("missing_game", "Both Asterion missions required")
        if not project.extensions or "org.drawtemp.example.asterion" not in project.extensions:
            raise PlatformGateError("missing_contract", "Second-game extension is required")
        if len(content.archetypes) < 4 or len(content.skills) < 3:
            raise PlatformGateError("missing_game", "Missing reusable class/enemy definitions")

        # GameSession smoke exercises actual campaign dialogue + first battle.
        start = Simulation.new(content, project, R24_CAMPAIGN, seed=seeds[0])
        if start.snapshot().scene is None or (
                "signal_depot" in start.snapshot().missions):
            raise PlatformGateError("invalid_entry", "Initial campaign dialogue was not presented")
        start.choose_story_option("launch")
        if R24_FIRST_MISSION not in start.snapshot().missions:
            raise PlatformGateError("invalid_entry", "Launch did not unlock first mission")
        start.start_mission(R24_FIRST_MISSION)
        if start.snapshot().mode != "battle":
            raise PlatformGateError("invalid_battle", "Actual first mission did not start")
        second_project = (asdict(project)["campaigns"][0]["start_mission"] == R24_FIRST_MISSION)

        with TemporaryDirectory(prefix="drawtemp-r24d-") as tmp:
            root = Path(tmp)
            edit = AuthoringSession.new(content, project)
            initial = edit.snapshot().to_dict()
            plan = edit.preview_project(
                lambda value: {**value, "subtitle": "Projet personnalisé via le Studio"},
                kind="r24d.second-game-edit")
            edit.apply(plan)
            edited = edit.snapshot().to_dict()
            if edit.revision != 1 or edited["project"]["subtitle"] == initial["project"]["subtitle"]:
                raise PlatformGateError("authoring_failed", "Expected one real Studio history step")
            edit.undo()
            if edit.snapshot().to_dict()["project"] != initial["project"]:
                raise PlatformGateError("undo_failed", "Undo differs from original GameProject")
            edit.redo()
            if edit.snapshot().to_dict()["project"] != edited["project"]:
                raise PlatformGateError("redo_failed", "Redo differs from edited GameProject")
            destination = root / "game.json"
            edit.save_as(destination)
            loaded = AuthoringSession.open(destination)
            if loaded.snapshot().to_dict()["project"] != edited["project"]:
                raise PlatformGateError("roundtrip_failed", "Saved project differs from Studio snapshot")
            export_check = preflight(destination)
            if not export_check["passed"]:
                raise PlatformGateError("preflight_failed", "; ".join(export_check["errors"]))

            # Real tactical sessions, replayed and reloaded from disk after
            # *each* operation by the canonical R1.E certification routine.
            seeds_report = []
            for seed in seeds:
                report = certify_trace(content, project, R24_CAMPAIGN,
                                       R24_TRACE, seed=seed)
                if (not report.verified or len(report.steps) != len(R24_TRACE) + 1 or
                        report.steps[-1].mode != "battle" or
                        report.steps[-1].rng_sha256 is None or
                        report.steps[-1].ct_sha256 is None):
                    raise PlatformGateError("replay_failed", "Incomplete tactical certification")
                fast_report = verify_sequence(content, project, R24_CAMPAIGN,
                                              R24_TRACE, seed=seed)
                if (not fast_report.verified or
                        len(fast_report.checkpoints) != len(R24_TRACE) + 1):
                    raise PlatformGateError(
                        "replay_failed", "Independent replay checkpoints incomplete")
                seeds_report.append({
                    "seed": seed, "commands": len(R24_TRACE),
                    "disk_resumed_each_step": True,
                    "simulation_sha256": report.final_sha256,
                    "rng_sha256": report.steps[-1].rng_sha256,
                    "ct_sha256": report.steps[-1].ct_sha256,
                })
    except PlatformGateError:
        raise
    except (ValueError, TypeError, KeyError, OSError, AssertionError) as exc:
        raise PlatformGateError("software_gate_failed", str(exc)) from exc

    return {
        "schema": 1, "kind": "drawtemp-r24-second-game",
        "game_id": R24_SECOND_GAME,
        "content_schema": 1, "project_schema": 1,
        "content_sha256": _sha(document),
        "project_sha256": _sha(manifest),
        "campaign_id": R24_CAMPAIGN,
        "missions": sorted(content.missions),
        "archetypes": sorted(content.archetypes),
        "tests": {
            "independent_content_fixture": True,
            "canonical_content_project": True,
            "sdk_semver": True,
            "first_mission_started": True,
            "studio_preview_apply_undo_redo": True,
            "studio_file_roundtrip": True,
            "creator_export_preflight": True,
            "multi_seed_replay_and_disk_restore": True,
            "existing_renderer_and_player_contracts": second_project,
        },
        "seeds": seeds_report,
        "software_passed": True,
        "native_player_export_certified": False,
        "gpu_visual_certified": False,
        "art_licenses_certified": False,
        "release_certified": False,
        "release_blockers": list(MANUAL_RELEASE_REQUIREMENTS),
    }
