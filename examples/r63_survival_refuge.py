"""VS-63 — deterministic shelter/exploration/crafting vertical slice.

Two-scene campaign, two recipes, environmental cold, failed gathering,
resource-paid recovery, canonical save/load and receipt idempotence.
No Qt, external assets or speculative rewards; run with:
    python -m examples.r63_survival_refuge
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.survival_authoring import (
    preview_survival_design, apply_survival_design)
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import RuleError
from sporebound.survival import EXTENSION


def survival_document():
    return {
        "version": 1,
        "needs": {
            "energy": 90, "hunger": 80, "temperature": 75,
            "energy_drain": 1, "hunger_drain": 1, "cold_drain": 1,
        },
        "items": ["wood", "stone", "berries", "camp", "ration"],
        "tools": [],
        "nodes": [
            {"id": "forest", "scene": "arrival", "item": "wood",
             "stock": 2, "yield": 1, "tool": None, "wear": 0,
             "energy_cost": 4, "cold": 8, "pos": [0, 0]},
            {"id": "quarry", "scene": "arrival", "item": "stone",
             "stock": 2, "yield": 1, "tool": None, "wear": 0,
             "energy_cost": 4, "cold": 0, "pos": [0, 1]},
            {"id": "bush", "scene": "arrival", "item": "berries",
             "stock": 4, "yield": 2, "tool": None, "wear": 0,
             "energy_cost": 2, "cold": 0, "pos": [0, 2]},
            {"id": "windfall", "scene": "outpost", "item": "wood",
             "stock": 1, "yield": 1, "tool": None, "wear": 0,
             "energy_cost": 2, "cold": 22, "pos": [0, 0]},
        ],
        "recipes": [
            {"id": "build_camp", "inputs": {"wood": 1, "stone": 1},
             "outputs": {"camp": 1}, "energy_cost": 3},
            {"id": "cook_ration", "inputs": {"berries": 2},
             "outputs": {"ration": 1}, "energy_cost": 3},
        ],
        "shelters": [
            {"id": "refuge", "scene": "arrival", "fuel": {"camp": 1},
             "energy_restore": 40, "warmth": 45, "pos": [1, 1]},
        ],
        "foods": [{"item": "ration", "nutrition": 22}],
    }


def build_example():
    content, project = reference_project()
    project.story["entry_scenes"] = {}
    project.story["scenes"].append({
        "id": "outpost", "title": "Falaises glacées", "speaker": "Explorateur",
        "text": "Le vent rend le retour difficile.",
        "choices": [{"id": "continue", "label": "Continuer"}],
    })
    for scene, title in (("arrival", "Refuge forestier"),
                         ("outpost", "Falaises glacées")):
        project.exploration[scene] = {
            "title": title, "theme": "village", "width": 4, "height": 4,
            "start": [0, 1], "blocked": [[2, 1]],
            "interactions": [
                {"id": "exit", "title": "Sentier", "text": "Poursuivre",
                 "pos": [1, 2], "required": False, "exit": True},
            ],
        }
    project.game_modes = {
        "version": 1, "default": {"preset": "srpg"},
        "scenes": {
            "arrival": {"preset": "action"},
            "outpost": {"preset": "action"},
        },
    }
    project.scene_routes = {
        "version": 1, "start": "arrival",
        "links": [
            {"id": "to_outpost", "source": "arrival",
             "destination": "outpost", "spawn": [0, 1]},
            {"id": "return_camp", "source": "outpost",
             "destination": "arrival", "spawn": [0, 1]},
        ],
    }
    project.validate(content)
    studio = AuthoringSession(content, project)
    preview = preview_survival_design(
        studio, survival_document(), expected_revision=studio.revision)
    if preview.report["recipes"] < 2 or preview.report["hazards"] < 1:
        raise AssertionError("VS-63 lacks two recipes or a cold hazard")
    apply_survival_design(studio, preview)
    canonical = GameProject.from_dict(
        studio.snapshot().to_dict()["project"], content)
    assert EXTENSION in canonical.extensions
    return content, canonical


def run_demo(seed=63):
    content, project = build_example()
    session = GameSession.new(content, project, "main", seed=seed)
    if "survival" not in session.recording():
        raise AssertionError("R63 opt-in checkpoint must be present")
    for node, receipt in (
        ("forest", "vs63-wood"), ("quarry", "vs63-stone"),
        ("bush", "vs63-berries"),
    ):
        if not session.survival_gather(node, receipt):
            raise AssertionError("Required resource not collected: " + node)
    if not session.survival_craft("build_camp", "vs63-camp"):
        raise AssertionError("Camp could not be crafted")
    if not session.survival_craft("cook_ration", "vs63-ration"):
        raise AssertionError("Ration could not be crafted")
    assert session.progress.inventory["camp"] == 1
    assert session.progress.inventory["ration"] == 1

    session.route_transition("to_outpost")
    # Long, cold exploration reaches genuine, recoverable exhaustion.
    session.survival_advance(90)
    exhaustion = session.survival_condition()
    if exhaustion["phase"] != "incapacitated":
        raise AssertionError("Unprotected cold exploration did not incapacitate")
    before_failure = session.recording()
    try:
        session.survival_gather("windfall", "vs63-exhausted-harvest")
    except RuleError:
        pass
    else:
        raise AssertionError("Exhausted survivor illegally harvested resources")
    if session.recording() != before_failure:
        raise AssertionError("Rejected survival action mutated checkpoint")

    session.route_transition("return_camp")
    # A return is not an automatic heal: spend a *crafted* ration and camp.
    if not session.survival_eat("ration", "vs63-meal"):
        raise AssertionError("Crafted meal did not restore hunger")
    if not session.survival_rest("refuge", "vs63-rest"):
        raise AssertionError("Refuge failed to restore warmth and energy")
    if session.survival_condition()["phase"] == "incapacitated":
        raise AssertionError("Survival resources did not permit recovery")
    after_recovery = session.recording()

    with TemporaryDirectory(prefix="drawtemp-vs63-") as directory:
        path = Path(directory) / "survival.json"
        session.save(path)
        restored = GameSession.load(path, content, project)
    if restored.recording() != after_recovery:
        raise AssertionError("R63 persistent progress differs after load")
    if restored.survival_eat("ration", "vs63-meal"):
        raise AssertionError("Receipt replay duplicated meal")
    if restored.survival_rest("refuge", "vs63-rest"):
        raise AssertionError("Receipt replay duplicated shelter")
    if restored.progress.inventory.get("camp", 0) != 0 or (
            restored.progress.inventory.get("ration", 0) != 0):
        raise AssertionError("Consumed rewards reappeared after reload")
    if restored.route_history != ["to_outpost", "return_camp"]:
        raise AssertionError("Exploration/return route did not persist")

    survival = restored.survival_state()
    return {
        "slice": "VS-63",
        "seed": seed,
        "route": list(restored.route_history),
        "recipes_used": ["build_camp", "cook_ration"],
        "hazard": "cold",
        "exhaustion_phase": exhaustion["phase"],
        "recovery_phase": restored.survival_condition()["phase"],
        "remaining_stocks": survival["stock"],
        "needs": survival["needs"],
        "tick": survival["tick"],
        "inventory": {
            k: v for k, v in sorted(restored.progress.inventory.items())
            if k in project.extensions[EXTENSION]["data"]["items"] and v
        },
        "receipts": len(survival["journal"]),
        "save_replay_equal": restored.recording() == after_recovery,
        "no_duplicate_rewards": True,
    }


def main():
    print(json.dumps(run_demo(), indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
