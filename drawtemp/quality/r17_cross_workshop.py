"""R17.12 cross-workshop Jeanne authoring, Player persistence and export evidence.

The same canonical AuthoringSession is edited by map, construction, RPG
database, event, campaign and cinematic tools. The exported game is a
*preview*, never an attested release: production asset rights remain pending.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
from importlib.resources import files
import json
from pathlib import Path
import shutil

from drawtemp.core import Content, GameProject
from drawtemp.export.r15 import preflight, verify_bundle
from drawtemp.player.qt_app import build_controller
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.construction import ConstructionWorkspace
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.events import EventStudio
from drawtemp.studio.map_authoring import MapStudio
from drawtemp.studio.rpg_database import lancer_example
from sporebound.event_composer import action, condition
from sporebound.game_session import GameSession
from sporebound.iso_structures import structure_template, validate_structure_placement
from sporebound.tactical_rpg3 import authored_rules_for_document

EVENT_ID = "r1712_gate"
PAGE_ID = "opened"
STORY_ID = "r1712_story"
CINEMATIC_ID = "r1712_cinematic"
ASSET_ID = "r1712_real_sprite"


def _sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _attached_real_asset(folder, session):
    """Copy an actual checked-in PNG, not a fabricated PNG header or sprite."""
    resource = files("sporebound").joinpath("content")
    published = json.loads(resource.joinpath("jeanne.game.json").read_text(encoding="utf-8"))
    sprites = (entry for entry in published["assets"]["entries"]
               if entry["kind"] == "sprite")
    for entry in sprites:
        original = resource.joinpath(*entry["path"].split("/"))
        if original.is_file():
            path = Path(folder).joinpath(*entry["path"].split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            with original.open("rb") as stream, path.open("wb") as target:
                shutil.copyfileobj(stream, target)
            copied = dict(entry)
            copied["id"] = ASSET_ID
            session.apply(session.preview_project(
                lambda project: {**project, "assets": {
                    "version": 1, "entries": [copied], "bindings": {}}},
                kind="r17.12-asset"))
            return entry["path"], _sha(path)
    raise AssertionError("No actual packaged Jeanne sprite PNG exists")


def author_project(folder):
    """Produce a real, cross-workshop authored two-document game on disk."""
    root = Path(folder)
    root.mkdir(parents=True, exist_ok=True)
    target = root / "r1712-jeanne.json"
    if target.exists():
        raise FileExistsError("Never overwrite an authored project: " + str(target))
    content, project = reference_project()
    session = AuthoringSession.new(content, project)
    maps = MapStudio(session, MISSION)
    maps.rename("R17.12 — Le passage du château")
    maps.paint([(1, 4)], "surface:sand")

    construction = ConstructionWorkspace(session, MISSION)
    clip = structure_template("Maison")
    current = session.snapshot().to_dict()["content"]
    mission = next(row for row in current["missions"] if row["id"] == MISSION)
    placed = False
    for y in range(mission["board"]["height"] - clip.height + 1):
        for x in range(mission["board"]["width"] - clip.width + 1):
            try:
                validate_structure_placement(current, MISSION, clip, (x, y))
            except (ValueError, RuntimeError):
                continue
            construction.apply(construction.preview_place("Maison", (x, y)))
            placed = True
            break
        if placed:
            break
    if not placed:
        raise AssertionError("R17.12 needs a valid construction footprint")
    house = construction.inspect()
    construction.apply(construction.preview_material(
        facade="torchis", roof="ardoise"))
    construction.apply(construction.preview_floor_add(1))

    # Real class/skill/equipment authoring, in the same session/revision.
    lancer_example(session)

    events = EventStudio(session)
    events.gate_wizard(
        MISSION, door_id="gate", lever_id="lever", lever_cell=[2, 4],
        event_id=EVENT_ID, danger_cell=[1, 3], danger=7,
        dialogue="Jeanne ouvre la porte", cinematic_id=CINEMATIC_ID)
    events.add_page(
        MISSION, EVENT_ID, page_id=PAGE_ID, priority=70,
        condition=condition("interact", object_id="lever"),
        actions=[action("message", text="Le passage est libre"),
                 action("hazard", pos=[1, 3], amount=7)])
    events.create_scene(
        MISSION, STORY_ID, "La porte du château", "Jeanne, entrez !",
        speaker="Garde")
    events.bind_scene(MISSION, EVENT_ID, STORY_ID)
    events.add_presentation_cue(
        MISSION, EVENT_ID, clip_id=CINEMATIC_ID,
        clip_name="Ouverture du château", kind="sound",
        cue_id="r1712_bell", fields={"cue": "bell"})

    session.apply(session.preview_project(
        lambda project: {**project,
                         "title": "R17.12 — Jeanne E2E",
                         "campaigns": [
                             {**campaign, "name": "Le passage du château"}
                             if campaign["id"] == "main" else campaign
                             for campaign in project["campaigns"]]},
        kind="r17.12-campaign"))
    asset_path, asset_sha = _attached_real_asset(root, session)

    maps.save_as(target)
    documents = session.snapshot().to_dict()
    assert not documents["dirty"]
    reloaded = AuthoringSession.open(target).snapshot().to_dict()
    assert documents["content"] == reloaded["content"]
    assert documents["project"] == reloaded["project"]
    checked_content = Content.from_dict(
        reloaded["content"], rules=authored_rules_for_document(reloaded["content"]))
    GameProject.from_dict(reloaded["project"], checked_content)
    return {"content_path": str(target), "project_path": str(target.with_suffix(".game.json")),
            "mission": MISSION, "house_id": house.structure_id,
            "asset_path": asset_path, "asset_sha256": asset_sha,
            "content_sha256": _sha(target),
            "project_sha256": _sha(target.with_suffix(".game.json")),
            "authoring_revision": session.revision}


def verify_gameplay(content_path, save_dir):
    """Real canonical R12 Player, manual checkpoint and independent resume."""
    source = Path(content_path)
    game = build_controller(content_path=source, save_dir=save_dir, campaign_id="main")
    assert game.new_game()["screen"] == "dialogue"
    game.choose("enter")
    game.start_mission(MISSION)
    before = game.state()["battle"]
    assert not next(obj for obj in before["objects"] if obj["id"] == "gate").get("open", False)
    game.interact_object("lever")
    fired = game.state()
    assert fired["screen"] == "dialogue" and fired["scene"]["id"] == STORY_ID
    assert next(obj for obj in fired["battle"]["objects"] if obj["id"] == "gate")["open"]
    game.save(1)
    save_path = Path(save_dir) / "slot_1.json"
    recording = GameSession.load(save_path, game.content, game.project).recording()
    original = game.session.recording()
    assert recording == original

    independent = build_controller(
        content_path=source, save_dir=save_dir, campaign_id="main")
    assert independent.load(1)["battle"] == fired["battle"]
    assert independent.session.recording() == original
    independent.choose("continue")
    assert independent.state()["screen"] == "battle"
    independent.save(1)
    loaded = GameSession.load(save_path, independent.content, independent.project)
    triggered = [row for row in loaded.active_battle.events
                 if row["kind"] == "trigger" and row.get("id") == EVENT_ID]
    assert len(triggered) == 1 and triggered[0]["page"] == PAGE_ID
    assert next(obj for obj in independent.state()["battle"]["objects"]
                if obj["id"] == "gate")["open"]
    assert build_controller(
        content_path=source, save_dir=save_dir,
        campaign_id="main").load(1)["screen"] == "battle"
    return {"save_sha256": _sha(save_path),
            "session_sha256": loaded.recording()["digest"],
            "trigger_count": len(triggered),
            "active_mission": MISSION, "replay_verified": True}


def inspect_export(content_path, bundle):
    """Check exported bytes, not source checkout, without granting legal rights."""
    report = preflight(content_path, require_licenses=False)
    if not report["passed"]:
        raise AssertionError("R17.12 preflight: " + str(report["errors"]))
    manifest = verify_bundle(bundle)
    source = Path(content_path)
    if manifest["content"] != "game/" + source.name:
        raise AssertionError("Wrong authored Content in bundle")
    physical = json.loads(Path(source.with_suffix(".game.json")).read_text(encoding="utf-8"))
    assets = {entry["path"] for entry in physical["assets"]["entries"]
              if entry["kind"] != "animation"}
    if not assets or not all((Path(bundle) / "game" / rel).is_file() for rel in assets):
        raise AssertionError("Real authored assets missing from exported bundle")
    if _sha(Path(bundle) / manifest["content"]) != _sha(source):
        raise AssertionError("Published Content no longer matches authoring")
    if _sha(Path(bundle) / "game" / source.with_suffix(".game.json").name) != _sha(
            source.with_suffix(".game.json")):
        raise AssertionError("Published project no longer matches authoring")
    return {"bundle_content": manifest["content"],
            "bundle_files": len(manifest["files"]),
            "asset_files": sorted(assets),
            "warnings": report["warnings"],
            "release_certified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description="R17.12 cross-workshop evidence")
    parser.add_argument("--project-dir", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--verify-bundle", type=Path,
                        help="Validate the exported authored bundle, without rewriting the project")
    args = parser.parse_args(argv)
    if args.verify_bundle:
        result = inspect_export(args.project_dir / "r1712-jeanne.json",
                                args.verify_bundle)
    else:
        result = author_project(args.project_dir)
        result["player"] = verify_gameplay(result["content_path"],
                                           args.project_dir / "saves")
        result["preflight"] = preflight(result["content_path"])
    result["r17_12_certified"] = False
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
