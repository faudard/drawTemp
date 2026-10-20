"""R55.C headless VS-55 micro-economy, using canonical Studio and Player APIs.

This example is not a release certificate. It builds a two-scene game project,
authors the resources through AuthoringSession, advances via fixed Player
movement ticks, trades, fulfills a quest and verifies a save/reload.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.system_design_authoring import (
    apply_system_design, preview_system_design)
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.system_design import EXTENSION


def build_example():
    content, project = reference_project()
    project.story["entry_scenes"] = {}
    project.story["scenes"].append({
        "id": "outpost", "title": "Vers l'avant-poste", "speaker": "Marchand",
        "text": "La route reste ouverte.", "choices": [
            {"id": "continue", "label": "Continuer"},
        ],
    })
    for name, title in (("arrival", "Village des forgerons"),
                        ("outpost", "Avant-poste")):
        project.exploration[name] = {
            "title": title, "theme": "village", "width": 4, "height": 4,
            "start": [0, 1], "blocked": [[2, 1]],
            "interactions": [
                {"id": "exit", "title": "Passage", "text": "Continuer",
                 "pos": [1, 2], "required": False, "exit": True},
            ],
        }
    project.game_modes = {
        "version": 1, "default": {"preset": "srpg"},
        "scenes": {"arrival": {"preset": "action"},
                   "outpost": {"preset": "action"}},
    }
    project.scene_routes = {
        "version": 1, "start": "arrival", "links": [
            {"id": "go_outpost", "source": "arrival",
             "destination": "outpost", "spawn": [0, 1]},
            {"id": "go_market", "source": "outpost",
             "destination": "arrival", "spawn": [0, 1]},
        ],
    }
    project.validate(content)
    system = {
        "version": 1,
        "resources": [
            {"id": "ore", "initial": 8, "capacity": 20},
            {"id": "ingot", "initial": 0, "capacity": 20},
            {"id": "gem", "initial": 0, "capacity": 10},
        ],
        "producers": [
            {"id": "smelter", "inputs": {"ore": 2},
             "outputs": {"ingot": 1}, "interval": 2},
            {"id": "jeweler", "inputs": {"ingot": 2},
             "outputs": {"gem": 1}, "interval": 3},
        ],
        "merchants": [
            {"id": "trader", "resource": "ingot", "scene": "arrival",
             "buy_price": 5, "sell_price": 2},
        ],
        "quests": [
            {"id": "delivery", "resource": "ingot",
             "quantity": 2, "flag": "delivered_ingots"},
        ],
    }
    studio = AuthoringSession(content, project)
    preview = preview_system_design(
        studio, system, expected_revision=studio.revision)
    apply_system_design(studio, preview)
    assert EXTENSION in studio.snapshot().to_dict()["project"]["extensions"]
    canonical_project = GameProject.from_dict(
        studio.snapshot().to_dict()["project"], content)
    return content, canonical_project


def run_demo():
    content, project = build_example()
    session = GameSession.new(content, project, "main", seed=55)
    # The example's grant is an explicit sample setup, not an economy reward.
    session.progress.gold = 100
    for _ in range(2):
        session.route_realtime_step(0, 0)
    session.route_transition("go_outpost")
    for _ in range(2):
        session.route_realtime_step(0, 0)
    if session.system_state()["stocks"]["ingot"] != 2:
        raise AssertionError("Smelter production did not follow Player ticks")
    session.route_transition("go_market")
    if not session.system_trade("trader", "buy", 2, "vs55-purchase"):
        raise AssertionError("First purchase must commit")
    if not session.system_fulfill("delivery"):
        raise AssertionError("Quest must commit exactly once")
    before_save = session.recording()
    with TemporaryDirectory(prefix="drawtemp-r55-") as temp:
        path = Path(temp) / "game.json"
        session.save(path)
        restored = GameSession.load(path, content, project)
    if restored.recording() != before_save:
        raise AssertionError("GameSession checkpoint did not round-trip")
    if restored.system_trade("trader", "buy", 2, "vs55-purchase"):
        raise AssertionError("Receipt replay duplicated purchased resources")
    if restored.system_fulfill("delivery"):
        raise AssertionError("Quest replay duplicated the reward")
    final = restored.system_state()
    return {
        "slice": "VS-55", "seed": 55, "scenes": ["arrival", "outpost", "arrival"],
        "economy_ticks": final["tick"],
        "stocks": final["stocks"],
        "gold": restored.progress.gold,
        "delivered_flag": restored.progress.story_flags["delivered_ingots"],
        "journal_count": len(final["journal"]),
        "save_reload_equal": restored.recording() == before_save,
        "duplicate_purchase_prevented": True,
        "duplicate_quest_prevented": True,
    }


def main():
    print(json.dumps(run_demo(), indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
