"""R60.B1 headless production smoke — real RPG, R55 shop, CT, save/replay.

Launch: python -m examples.r60_production_showcase
No fake battles or in-memory-only rewards; no 10.0 certification.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from drawtemp.export.templates import create_template
from drawtemp.sdk.authoring import AuthoringSession
from sporebound.ai import choose_command
from sporebound.game_session import GameSession


def _win_rpg(session, encounter):
    target = "loup" if encounter == "woods" else "gardien"
    session.rpg_start(encounter)
    session.rpg_action({
        "kind": "combo", "actor": session.rpg_state()["active"],
        "target": target, "combo": "lames_du_relais"})
    for _ in range(45):
        current = session.rpg_state()
        if current["result"]:
            break
        session.rpg_action({"kind": "attack", "actor": current["active"],
                            "target": target})
    if session.rpg_state()["result"] != "victory":
        raise AssertionError("RPG victory must be reached by native commands")
    session.rpg_finish()


def _win_ct(session):
    for _ in range(160):
        if session.battle.result is not None:
            break
        battle = session.active_battle
        if battle.active is not None and battle.active.team == "enemy":
            session.ai_turn()
        else:
            session.execute(choose_command(battle))
    if session.battle.result != "victory" or not session.finalized:
        raise AssertionError("CT victory must be reached by native commands")


def run_showcase(seed=17):
    """End-to-end headless acceptance; never modifies a historical project."""
    with TemporaryDirectory(prefix="drawtemp-r60b1-") as folder:
        project_dir = create_template("hybrid_r60", Path(folder) / "original")
        editor = AuthoringSession.open(project_dir / "game.json")
        authored = editor.snapshot().to_dict()
        from sporebound.model import Content
        from sporebound.game_project import GameProject
        content = Content.from_dict(authored["content"])
        project = GameProject.from_dict(authored["project"], content)

        game = GameSession.new(content, project, "main", seed=seed)
        start_gold = game.progress.gold
        for _ in range(4):
            game.route_realtime_step(0, 0)
        if game.system_state()["stocks"]["lantern"] != 2:
            raise AssertionError("Lantern workshop did not produce two lanterns")

        game.route_transition("village_to_woods")
        _win_rpg(game, "woods")
        game.route_transition("woods_to_village")
        if not game.system_trade("artisan_village", "buy", 2, "r60_purchase_01"):
            raise AssertionError("First lantern purchase must apply")
        if not game.system_fulfill("relight_beacon"):
            raise AssertionError("Beacon material quest must apply")

        checkpoint = game.recording()
        path = Path(folder) / "checkpoint.json"
        game.save(path)
        game = GameSession.load(path, content, project)
        if game.recording() != checkpoint:
            raise AssertionError("Shop/quest checkpoint divergence")
        if game.system_trade("artisan_village", "buy", 2, "r60_purchase_01"):
            raise AssertionError("Duplicate receipt was unexpectedly applied")
        if game.system_fulfill("relight_beacon"):
            raise AssertionError("Beacon was supplied more than once")

        game.route_transition("village_to_woods")
        game.route_transition("woods_to_crypt")
        _win_rpg(game, "crypt")
        game.route_transition("crypt_to_ct")
        if game.party_hybrid_state()["phase"] != "TACTICAL_CT":
            raise AssertionError("Native CT scene was not entered")
        pre_ct = game.recording()
        game.save(path)
        game = GameSession.load(path, content, project)
        if game.recording() != pre_ct:
            raise AssertionError("CT checkpoint divergence")
        _win_ct(game)
        game.return_to_campaign()
        game.route_transition("ct_victory_to_village")
        game.rpg_claim_quest()
        if game.progress.gold != start_gold + 60:
            # Original R53 RPG/CT/quest yields 12+24+9+25 = 70.
            # Buying lanterns consumes 10 gold; the R55 quest pays no gold.
            raise AssertionError("Unexpected non-idempotent reward ledger")
        if not game.progress.story_flags.get("beacon_supplied"):
            raise AssertionError("Beacon quest flag not persisted")
        final = game.recording()
        game.save(path)
        loaded = GameSession.load(path, content, project)
        if loaded.recording() != final:
            raise AssertionError("Final end-to-end replay divergence")
        return {
            "slice": "VS-60.B1", "seed": seed,
            "project": project.title,
            "areas": sorted(project.exploration),
            "modes": ["FREE_REALTIME", "RPG_TURN", "TACTICAL_CT"],
            "hud_layouts": sorted(project.extensions["org.drawtemp.ui"]["data"]["layouts"]),
            "beacon_supplied": True,
            "ct_completed": True,
            "economy_ticks": loaded.system_state()["tick"],
            "gold_delta": loaded.progress.gold - start_gold,
            "replay_roundtrip": True,
            "status": "headless_slice_only_not_release_certified",
        }


def main():
    print(json.dumps(run_showcase(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
