"""R45.C — runnable seven-day village, built only from canonical authored data.

No test fixture imports, no alternate economy or Player save format. Export the
two-file Content/GameProject pair and launch it in the standard Qt Player.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from drawtemp.sdk.reference import MISSION, reference_project
from sporebound.game_session import GameSession
from sporebound.living_world import EXTENSION
from sporebound.model import RuleError


def village_project():
    """Return a validated, opt-in market and off-focus outskirts scene."""
    content, project = reference_project()
    project.title = "R45 — Sept jours au marché"
    project.subtitle = "Artisanat, livraisons et prix sur sept journées"
    project.story["entry_scenes"] = {}
    # Exploration stages must also resolve to canonical R9 narrative scene IDs.
    project.story["scenes"].append({
        "id": "outskirts", "title": "Aux abords du village",
        "speaker": "Jeanne", "text": "Le chemin traverse les collines.",
        "choices": [{"id": "continue", "label": "Continuer"}]})
    project.exploration["arrival"] = {
        "title": "Place du marché", "theme": "village",
        "width": 4, "height": 4, "start": [0, 1],
        "blocked": [[2, 1]],
        "interactions": [{
            "id": "exit", "title": "Chemin de la forêt",
            "text": "Un sentier mène vers les collines.",
            "pos": [1, 2], "required": False, "exit": True}]}
    project.exploration["outskirts"] = {
        "title": "Aux abords du village", "theme": "forest",
        "width": 4, "height": 4, "start": [1, 1],
        "blocked": [[3, 1]],
        "interactions": [{
            "id": "return_sign", "title": "Retour au marché",
            "text": "Le chemin revient à la place.",
            "pos": [1, 2], "required": False, "exit": True}]}
    project.game_modes = {
        "version": 1, "default": {"preset": "srpg"},
        "scenes": {"arrival": {"preset": "action"},
                   "outskirts": {"preset": "action"},
                   MISSION: {"preset": "srpg"}}}
    project.scene_routes = {
        "version": 1, "start": "arrival",
        "links": [
            {"id": "to_outskirts", "source": "arrival",
             "destination": "outskirts", "spawn": [1, 1]},
            {"id": "to_market", "source": "outskirts",
             "destination": "arrival", "spawn": [1, 1]},
        ]}
    project.extensions[EXTENSION] = {
        "schema_version": 1, "references": [],
        "data": {
            "version": 1, "start_minute": 480,
            "ticks_per_minute": 2,
            "clock_policy": "exploration_only",
            "starting_gold": 100,
            "npcs": [
                {"id": "merchant", "schedule": [
                    {"minute": 0, "scene": "arrival", "activity": "home"},
                    {"minute": 480, "scene": "arrival", "activity": "trade"},
                    {"minute": 1020, "scene": "arrival", "activity": "home"}]},
                {"id": "artisan", "schedule": [
                    {"minute": 0, "scene": "arrival", "activity": "rest"},
                    {"minute": 480, "scene": "arrival", "activity": "work"},
                    {"minute": 1020, "scene": "arrival", "activity": "rest"}]},
                {"id": "traveler", "schedule": [
                    {"minute": 0, "scene": "outskirts", "activity": "rest"},
                    {"minute": 600, "scene": "outskirts", "activity": "walk"},
                    {"minute": 1100, "scene": "outskirts", "activity": "rest"}]},
            ],
            "factions": [{"id": "guild", "initial": 0}],
            "shops": [{
                "id": "village_shop", "npc": "merchant", "scene": "arrival",
                "activity": "trade", "faction": "guild",
                "min_reputation": 0,
                "items": [
                    {"id": "herb", "buy_price": 2, "sell_price": 1,
                     "daily_stock": 5},
                    {"id": "elixir", "buy_price": 12, "sell_price": 10,
                     "daily_stock": 3},
                ]}],
            "recipes": [{
                "id": "brew_elixir", "npc": "artisan", "scene": "arrival",
                "activity": "work", "faction": "guild", "min_reputation": 0,
                "inputs": [{"item": "herb", "quantity": 2}],
                "outputs": [{"item": "elixir", "quantity": 1}],
                "gold_cost": 2, "daily_limit": 2,
            }],
            "daily_quests": [{
                "id": "guild_delivery", "faction": "guild",
                "min_reputation": 0,
                "start_minute": 480, "end_minute": 1000,
                "completion_flag": "guild_delivered_on_day",
                "reward_gold": 20, "reputation_delta": 1,
                "delivery_item": "elixir", "delivery_quantity": 1,
            }],
        }}
    project.validate(content)
    return content, project


def export_village(directory):
    """Write a verified, portable authored pair; never write into a save slot."""
    content, project = village_project()
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    content_path = root / "market-r45.json"
    project_path = root / "market-r45.game.json"
    content_path.write_text(json.dumps(content.to_dict(), ensure_ascii=False,
                                       sort_keys=True, indent=2) + "\n",
                            encoding="utf-8")
    project.save(project_path, content)
    return content_path, project_path


def seven_day_gate(*, save_dir=None):
    """Deterministic proof: trade, produce, deliver, sell, resume and rollover.

    By design receipts stay in GameSession and a duplicate command cannot
    award gold or stock twice. This is a headless gate, not GPU/UX certification.
    """
    content, project = village_project()
    game = GameSession.new(content, project, "main", seed=45)
    assert game.progress.gold == 100
    history = []
    with TemporaryDirectory() as ephemeral:
        root = Path(save_dir) if save_dir else Path(ephemeral)
        root.mkdir(parents=True, exist_ok=True)
        checkpoint = root / "market-7-day-checkpoint.json"
        for day in range(7):
            world = game.living_world_state()
            assert world["day"] == day and world["minute"] == 480
            assert world["shops"][0]["open"]
            assert world["recipes"][0]["available"]
            assert world["shops"][0]["items"][0]["stock"] == 5
            assert world["recipes"][0]["remaining_today"] == 2
            assert len(game.living_world_state(scene="outskirts")["npcs"]) == 1
            game.living_world_trade(
                "village_shop", "herb", "buy", 2, "week_%s_herbs" % day)
            game.living_world_trade(
                "village_shop", "elixir", "buy", 1, "week_%s_elixir" % day)
            game.living_world_craft(
                "brew_elixir", 1, "week_%s_brew" % day)
            assert game.living_world_deliver_daily_quest("guild_delivery")
            assert not game.living_world_deliver_daily_quest("guild_delivery")
            game.living_world_trade(
                "village_shop", "elixir", "sell", 1, "week_%s_sell" % day)
            assert game.progress.gold == 100 + 12 * (day + 1)
            assert game.progress.inventory.get("herb") == 0
            assert game.progress.inventory.get("elixir") == 0
            assert game.living_world_state()["reputation"]["guild"] == day + 1
            history.append({
                "day": day + 1, "gold": game.progress.gold,
                "reputation": game.living_world_state()["reputation"]["guild"],
                "delivered": game.living_world_state()["daily_quests"][0]["claimed_today"]})
            recorded = game.recording()
            game.save(checkpoint)
            restored = GameSession.load(checkpoint, content, project)
            assert restored.recording() == recorded
            assert not restored.living_world_trade(
                "village_shop", "herb", "buy", 2, "week_%s_herbs" % day)
            assert not restored.living_world_craft(
                "brew_elixir", 1, "week_%s_brew" % day)
            assert not restored.living_world_deliver_daily_quest("guild_delivery")
            assert restored.recording() == recorded
            game = restored
            if day == 3:
                game.route_transition("to_outskirts")
                assert game.living_world_state(scene="outskirts")["npcs"]
                # Time passes with the merchant outside focus.
                game.living_world_advance(1440 * 2)
                game.route_transition("to_market")
            else:
                game.living_world_advance(1440 * 2)
    assert len(history) == 7 and history[-1]["gold"] == 184
    return {"days": history, "ending_gold": game.progress.gold,
            "ending_day": game.living_world_state()["day"],
            "ending_reputation": game.living_world_state()["reputation"]["guild"],
            "trades": len(game.recording()["living_world"]["trades"]),
            "crafts": len(game.recording()["living_world"]["crafts"])}


def main(argv=None):
    parser = argparse.ArgumentParser(description="R45 playable market + 7-day gate")
    parser.add_argument("--output", type=Path, help="Write the authored project pair")
    parser.add_argument("--gate", action="store_true", help="Run the seven-day test")
    args = parser.parse_args(argv)
    if not args.output and not args.gate:
        parser.error("Choose --output and/or --gate")
    if args.output:
        content_path, project_path = export_village(args.output)
        print("Content:", content_path)
        print("GameProject:", project_path)
        print("Launch: python -m drawtemp.player.qt_app --content",
              content_path, "--project", project_path, "--campaign main")
    if args.gate:
        print(json.dumps(seven_day_gate(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
