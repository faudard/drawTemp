"""R20.D — actual headless prologue -> Act I certification, no fake victories.

Gameplay must be driven by the normal GameSession/Exploration/Battle
contracts. The report is NOT a GPU, native-distribution, UX or license
certification. Exit non-zero on any incomplete route.
"""
from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from sporebound.ai import choose_command
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "sporebound/content/jeanne.json"
PROJECT = ROOT / "sporebound/content/jeanne.r20c.game.json"
MOVES = ((0, -1), (0, 1), (-1, 0), (1, 0))
# Covers both prologue choices, both companions, both tactical branches,
# both meaningful aftermath variants, and all three end-of-act outcomes.
CASES = {
    "archives_secours": {
        "prologue": "secourir", "companion": "engager_etienne",
        "pont": "tenir_passage", "hospice": "ravitailler",
        "dilemma": "prendre_archives", "aftermath": "consigner",
        "ending": "preuve_officielle", "final": "sceller_dossier",
        "conclusion": "preuves", "recruit": "etienne", "prologue_mission": "p0_03a_secours",
        "branch_mission": "a1_04a_archives", "branch_scene": "sc_r20c_archives",
        "ending_scene": "sc_r20c_fin_archives", "support": True,
    },
    "otages_poursuite": {
        "prologue": "poursuivre", "companion": "engager_agnes",
        "pont": "contourner", "hospice": "proteger_dossiers",
        "dilemma": "liberer_otages", "aftermath": "accueillir",
        "ending": "parole_otages", "final": "tenir_parole",
        "conclusion": "temoins", "recruit": "agnes", "prologue_mission": "p0_03b_poursuite",
        "branch_mission": "a1_04b_otages", "branch_scene": "sc_r20c_otages",
        "ending_scene": "sc_r20c_fin_otages", "support": False,
    },
    "foi_secours": {
        "prologue": "secourir", "companion": "engager_agnes",
        "pont": "tenir_passage", "hospice": "proteger_dossiers",
        "dilemma": "liberer_otages", "aftermath": "deposer",
        "ending": "appel_de_jeanne", "final": "partir_libre",
        "conclusion": "libre_arbitre", "recruit": "agnes", "prologue_mission": "p0_03a_secours",
        "branch_mission": "a1_04b_otages", "branch_scene": "sc_r20c_otages",
        "ending_scene": "sc_r20c_fin_foi", "support": True,
    },
    "archives_poursuite": {
        "prologue": "poursuivre", "companion": "engager_etienne",
        "pont": "contourner", "hospice": "ravitailler",
        "dilemma": "prendre_archives", "aftermath": "publier",
        "ending": "preuve_officielle", "final": "sceller_dossier",
        "conclusion": "preuves", "recruit": "etienne", "prologue_mission": "p0_03b_poursuite",
        "branch_mission": "a1_04a_archives", "branch_scene": "sc_r20c_archives",
        "ending_scene": "sc_r20c_fin_archives", "support": False,
    },
}


def require(value, message):
    if not value:
        raise AssertionError(message)


def visit(session, point_id):
    """Find a legal cardinal path through the authored, blocked cells."""
    stage = session.exploration_state()
    require(stage is not None and not stage["completed"], "Exploration missing")
    target = next((tuple(p["pos"]) for p in stage["interactions"]
                   if p["id"] == point_id), None)
    require(target is not None, "Missing hotspot: " + point_id)
    start = tuple(stage["position"])
    blocked = {tuple(p) for p in stage["blocked"]}
    queue = deque([(start, [])])
    seen = {start}
    route = None
    while queue:
        (x, y), steps = queue.popleft()
        if abs(x - target[0]) + abs(y - target[1]) <= 1:
            route = steps
            break
        for dx, dy in MOVES:
            other = x + dx, y + dy
            if (0 <= other[0] < stage["width"] and
                    0 <= other[1] < stage["height"] and
                    other not in blocked and other not in seen):
                seen.add(other)
                queue.append((other, steps + [(dx, dy)]))
    require(route is not None, "Unreachable hotspot: " + point_id)
    for dx, dy in route:
        session.explore_move(dx, dy)
    return session.explore_interact(point_id)


def clear_stage(session, *, rescue_id=None):
    stage = session.exploration_state()
    require(stage is not None and not stage["completed"], "Missing exploration stage")
    require(not session.available_choices(), "Choices leaked before exploration exit")
    if rescue_id is not None:
        actor = next((a for a in stage.get("actors", [])
                      if a["id"] == rescue_id), None)
        require(actor is not None, "Missing civilian: " + rescue_id)
        require(actor["status"] == "active", "Civilian expired too early")
        result = session.explore_actor(rescue_id, "rescue")
        require(result["rescued"], "Rescue was not committed")
    for point in stage["interactions"]:
        if point["required"]:
            visit(session, point["id"])
    exit_id = next(p["id"] for p in stage["interactions"] if p["exit"])
    require(visit(session, exit_id)["finished"], "Exit was not acknowledged")
    require(session.exploration_state()["completed"], "Stage is not complete")
    require(session.available_choices(), "Stage exit softlocked narrative")


def acknowledge_clips(session, clip_ids):
    """Playback ACK only; no story choice or battle result is implied."""
    while True:
        clip = session.pending_scene_cinematic()
        if clip is None:
            break
        current = clip["id"]
        before = (tuple(session.progress.completed),
                  tuple((x["scene"], x["choice"]) for x in session.progress.story_history),
                  tuple(session.progress.unlocked))
        session.acknowledge_scene_cinematic(current)
        after = (tuple(session.progress.completed),
                 tuple((x["scene"], x["choice"]) for x in session.progress.story_history),
                 tuple(session.progress.unlocked))
        require(before == after, "Cinematic ACK changed actual gameplay progress")
        require(current not in clip_ids, "Clip acknowledged more than once in route")
        clip_ids.append(current)


def checkpoint(session, folder, marker, content, project):
    """Write/read a genuine checkpoint, verifying the canonical digest."""
    location = folder / "checkpoint.json"
    session.save(location)
    verified = GameSession.load(location, content, project)
    require(verified.recording()["digest"] == session.recording()["digest"],
            "Checkpoint changed while replaying")
    require(verified.progress == session.progress, "Reload changed campaign state")
    return verified


def win(session, mission_id, folder, content, project, battles, *, max_commands=1100):
    require(session.available_missions() == [mission_id],
            "Unexpected available mission at " + mission_id +
            ": " + repr(session.available_missions()))
    battle = session.start_mission(mission_id)
    require(battle.mission.id == mission_id and battle.result is None,
            "Mission start did not open a real battle")
    # R16 replay verification also applies to an unfinished tactical session.
    session = checkpoint(session, folder, mission_id + "_battle_start",
                         content, project)
    commands = 0
    while session.active_battle.result is None and commands < max_commands:
        session.execute(choose_command(session.active_battle))
        commands += 1
    require(session.active_battle.result == "victory",
            f"{mission_id}: not victorious after {commands} real commands")
    require(session.finalized and mission_id in session.progress.completed,
            "Battle was not formally settled")
    require(session.active_battle.recording()["commands"] is not None,
            "Tactical replay journal missing")
    session.return_to_campaign()
    require(session.mode == "campaign", "Still in battle after return")
    battles.append({"mission": mission_id, "commands": commands,
                    "victory": True})
    return checkpoint(session, folder, mission_id + "_settled", content, project)


def run_case(content, project, name, cfg, folder):
    session = GameSession.new(content, project, "jeanne", seed=17)
    scenes, clips, battles = [], [], []
    def scene(expected):
        active = session.active_scene()
        require(active is not None and active["id"] == expected,
                "Expected " + expected + ", got " + repr(active))
        scenes.append(expected)
        acknowledge_clips(session, clips)

    def save(tag):
        nonlocal session
        session = checkpoint(session, folder, tag, content, project)

    def choose(option):
        session.choose_story_option(option)

    scene("sc_p0_champs")
    clear_stage(session)
    save("fields_explored")
    choose("ecouter" if cfg["prologue"] == "secourir" else "resister")
    scene("sc_p0_visions")
    choose("repondre")
    scene("sc_p0_fumee")
    choose("souvenir")
    session = win(session, "p0_01_lame", folder, content, project, battles)
    scene("sc_p0_apres_lecon")
    choose("courir")
    session = win(session, "p0_02_incendie", folder, content, project, battles)
    scene("sc_p0_cendres")
    clear_stage(session, rescue_id="colin" if cfg["support"] else None)
    save("village_explored")
    choose(cfg["prologue"])
    session = win(session, cfg["prologue_mission"], folder, content, project, battles)
    scene("sc_p0_apres_branche")
    choose("partir")
    session = win(session, "p0_04_fuite", folder, content, project, battles)
    scene("sc_p0_au_revoir")
    choose("promesse")
    require(session.progress.story_flags.get("prologue_complete") is True,
            "Prologue did not finalize")
    # This must be reached through the actual scene graph, not by overwriting
    # session.progress.story_pending with an Act-I fixture.
    scene("sc_a1_camp")
    clear_stage(session, rescue_id="eline" if cfg["support"] else None)
    save("camp_explored")
    choose(cfg["companion"])
    require(session.progress.story_flags.get("recruited_" + cfg["recruit"]) is True,
            "Companion not recruited through story")
    session = win(session, "a1_01_route", folder, content, project, battles)
    scene("sc_a1_pont")
    clear_stage(session, rescue_id="luc" if cfg["support"] else None)
    save("bridge_explored")
    choose(cfg["pont"])
    session = win(session, "a1_02_pont", folder, content, project, battles)
    scene("sc_a1_hospice")
    clear_stage(session, rescue_id="lucie" if cfg["support"] else None)
    save("hospice_explored")
    choose(cfg["hospice"])
    session = win(session, "a1_03_hospice", folder, content, project, battles)
    scene("sc_a1_dilemme")
    clear_stage(session)
    save("dilemma_explored")
    choose(cfg["dilemma"])
    session = win(session, cfg["branch_mission"], folder, content, project, battles)
    scene(cfg["branch_scene"])
    save("aftermath_before_choice")
    choose(cfg["aftermath"])
    require(session.progress.story_flags.get("r20c_route_after") ==
            ("archives" if cfg["dilemma"] == "prendre_archives" else "otages"),
            "Aftermath flags missing")
    scene("sc_a1_debrief")
    choose("avancer_vaucouleurs")
    session = win(session, "a1_05_vaucouleurs", folder, content, project, battles)
    scene("sc_a1_fin")
    choices = {x["id"] for x in session.available_choices()}
    require(cfg["ending"] in choices, "Expected ending locked")
    forbidden = ("parole_otages" if cfg["dilemma"] == "prendre_archives"
                 else "preuve_officielle")
    require(forbidden not in choices, "Wrong tactical branch unlocked the ending")
    choose(cfg["ending"])
    scene(cfg["ending_scene"])
    save("epilogue_before_choice")
    choose(cfg["final"])
    require(session.active_scene() is None, "Act I did not close its last scene")
    require(session.progress.story_flags.get("acte1_complete") is True,
            "Act I completion flag missing")
    require(session.progress.story_flags.get("acte2_route_ouverte") is True,
            "Act II handoff absent")
    require(session.progress.story_flags.get("r20c_act1_conclusion") == cfg["conclusion"],
            "Wrong ending persisted")
    require(len(session.progress.completed) == 9, "Missing completed missions")
    require(session.available_missions() == [], "Unexpected unlocked mission after ending")
    save("complete")
    require(session.active_scene() is None and
            session.progress.story_flags["acte1_complete"],
            "Terminal save did not round-trip")
    require(len(battles) == 9 and all(row["commands"] for row in battles),
            "A mission did not actually execute tactical commands")
    return {"name": name, "prologue": cfg["prologue"],
            "companion": cfg["recruit"],
            "branch": cfg["dilemma"], "ending": cfg["conclusion"],
            "scenes": scenes, "cinematics_acknowledged": clips,
            "battles": battles, "completed_missions": list(session.progress.completed),
            "save_load_verified": True, "status": "pass"}


def certify(*, names=None):
    content = Content.load(CONTENT)
    project = GameProject.load(PROJECT, content)
    selected = list(names) if names is not None else list(CASES)
    result = {"schema": 1, "kind": "r20d-jeanne-headless-acceptance",
              "content": "jeanne.json", "project": "jeanne.r20c.game.json",
              "cases": [], "passed": False,
              "release_certified": False,
              "not_evidenced": [
                  "real-screen Qt Player UX/GPU and accessibility",
                  "independent human playtest",
                  "native runtime on clean/offline machines",
                  "redistribution license rights for visual/audio assets",
                  "cross-platform installer and release go/no-go",
              ]}
    for name in selected:
        if name not in CASES:
            raise ValueError("Unknown acceptance path: " + name)
        try:
            with TemporaryDirectory(prefix="r20d-") as temp:
                result["cases"].append(run_case(
                    content, project, name, CASES[name], Path(temp)))
        except Exception as exc:
            result["cases"].append({"name": name, "status": "fail",
                                    "error": type(exc).__name__ + ": " + str(exc)})
    result["passed"] = all(case["status"] == "pass" for case in result["cases"])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=sorted(CASES),
                        action="append", help="Route to run, repeatable (default: all)")
    parser.add_argument("--report", type=Path,
                        help="Optional local JSON report path")
    args = parser.parse_args(argv)
    report = certify(names=args.case)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8")
    summary = {
        "passed": report["passed"], "release_certified": False,
        "cases": [{"name": c["name"], "status": c["status"],
                   **({"error": c["error"]} if "error" in c else
                      {"battle_count": len(c["battles"])})}
                  for c in report["cases"]],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
