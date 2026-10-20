"""R53.C1 — real R41 RPG -> R25 CT -> exploration hybrid regression.

This is a genuine three-hero, two-combat-mode route; no stub battle or fake
HP transfer. Each combat's HP is intentionally scoped to its native engine.
"""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.creator_examples.r53_hybrid import (
    CT_MISSION, THREE_HEROES, build_relais_hybride_r53,
)
from drawtemp.player.controller import PlayerController
from sporebound.ai import choose_command
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError


def _win_rpg(session, encounter):
    session.rpg_start(encounter)
    before = session.party_hybrid_state()
    assert before["phase"] == "RPG_TURN"
    assert len(before["members"]) == 3
    assert before["active_combos"] == ["lames_du_relais"], before
    actor = session.rpg_state()["active"]
    session.rpg_action({
        "kind": "combo", "actor": actor, "target":
        "loup" if encounter == "woods" else "gardien",
        "combo": "lames_du_relais"})
    for _ in range(45):
        view = session.rpg_state()
        if view["result"]:
            break
        session.rpg_action({
            "kind": "attack", "actor": view["active"],
            "target": "loup" if encounter == "woods" else "gardien"})
    assert session.rpg_state()["result"] == "victory", session.rpg_state()
    session.rpg_finish()


def _ct_step(session):
    battle = session.active_battle
    if battle.active is not None and battle.active.team == "enemy":
        session.ai_turn()
    else:
        session.execute(choose_command(battle))


def _win_ct(session):
    for _ in range(160):
        if session.battle.result is not None:
            break
        _ct_step(session)
    assert session.battle.result == "victory", (
        session.battle.result, session.battle.tick,
        [(u.id, u.hp) for u in session.battle.units])
    assert session.finalized


class R53HybridVerticalSliceTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = build_relais_hybride_r53()

    def test_three_heroes_two_native_modes_and_reward_once_two_seeds(self):
        for seed in (17, 31):
            with self.subTest(seed=seed):
                session = GameSession.new(self.content, self.project, "main",
                                          seed=seed)
                initial = session.party_hybrid_state()
                self.assertEqual(initial["phase"], "EXPLORATION")
                self.assertEqual([h["id"] for h in initial["members"]],
                                 list(THREE_HEROES))
                self.assertEqual([h["hp"] for h in initial["members"]],
                                 [None, None, None])
                self.assertEqual(session.party_orchestration_state()["leader"],
                                 "oren")
                self.assertEqual(initial["campaign_inventory"]["potion"], 1)
                session.party_switch_leader("mira")
                session.party_set_formation(["support", "front", "rear"])
                self.assertEqual(session.party_hybrid_state()["members"][2][
                    "leader"], True)
                self.assertEqual(session.party_hybrid_state()["members"][2][
                    "formation"], "rear")
                initial_gold = session.progress.gold
                # The same canonical R25 route allows R41 RPG fights in
                # the woods/crypt before the native CT mission gate opens.
                session.route_transition("village_to_woods")
                _win_rpg(session, "woods")
                self.assertEqual(session.progress.gold, initial_gold + 12)
                session.route_transition("woods_to_crypt")
                _win_rpg(session, "crypt")
                self.assertEqual(session.progress.gold, initial_gold + 36)
                self.assertEqual(session.progress.inventory["potion"], 1)
                self.assertEqual(session.rpg_available(), [])
                self.assertEqual(session.party_hybrid_state()["phase"],
                                 "EXPLORATION")
                rpg_end = session.recording()
                # Crash/restart at the RPG→CT boundary keeps the R25 cursor,
                # R41 reward flags, R53 formation and Campaign items intact.
                session = GameSession.from_recording(
                    rpg_end, self.content, self.project)
                self.assertEqual(session.recording(), rpg_end)

                session.route_transition("crypt_to_ct")
                self.assertEqual(session.mode, "battle")
                self.assertEqual(session.route_scene, CT_MISSION)
                self.assertEqual(session.party_hybrid_state()["phase"],
                                 "TACTICAL_CT")
                self.assertEqual([h["id"] for h in
                                  session.party_hybrid_state()["members"]],
                                 list(THREE_HEROES))
                self.assertTrue(all(h["hp"] is not None for h in
                                    session.party_hybrid_state()["members"]))
                with self.assertRaises(RuleError):
                    session.party_switch_leader("elya")
                with self.assertRaises(RuleError):
                    session.route_transition("ct_victory_to_village")
                saved = session.recording()
                with TemporaryDirectory() as folder:
                    path = Path(folder) / "r53-hybrid-ct.json"
                    session.save(path)
                    loaded = GameSession.load(path, self.content, self.project)
                    self.assertEqual(loaded.recording(), saved)
                    _ct_step(loaded)
                    middle = loaded.recording()
                    loaded.save(path)
                    loaded = GameSession.load(path, self.content, self.project)
                    self.assertEqual(loaded.recording(), middle)
                    self.assertEqual(loaded.progress.gold, initial_gold + 36)
                    _win_ct(loaded)
                    self.assertEqual(loaded.progress.gold, initial_gold + 45)
                    self.assertIn(CT_MISSION, loaded.progress.completed)
                    loaded.return_to_campaign()
                    with self.assertRaises(RuleError):
                        loaded.rpg_start("woods")
                    loaded.route_transition("ct_victory_to_village")
                    self.assertEqual(loaded.route_scene, "village")
                    self.assertEqual(loaded.party_hybrid_state()["phase"],
                                     "EXPLORATION")
                    self.assertEqual(loaded.progress.gold, initial_gold + 45)
                    self.assertEqual(loaded.progress.inventory["potion"], 1)
                    self.assertEqual(loaded.party_orchestration_state()[
                        "leader"], "mira")
                    loaded.rpg_claim_quest()
                    self.assertEqual(loaded.progress.gold, initial_gold + 70)
                    self.assertEqual(loaded.progress.inventory["potion"], 3)
                    self.assertTrue(loaded.rpg_quest_state()["completed"])
                    with self.assertRaises(RuleError):
                        loaded.rpg_claim_quest()
                    loaded.save(path)
                    final = GameSession.load(path, self.content, self.project)
                    self.assertEqual(final.recording(), loaded.recording())
                    self.assertEqual(final.route_scene, "village")
                    self.assertEqual(final.party_orchestration_state()[
                        "formation"], ["support", "front", "rear"])
                    self.assertEqual(final.progress.gold, initial_gold + 70)
                self.assertEqual(rpg_end["mode"], "campaign")

    def test_mid_rpg_checkpoint_and_forged_cross_mode_route(self):
        session = GameSession.new(self.content, self.project, "main", seed=17)
        session.route_transition("village_to_woods")
        session.rpg_start("woods")
        self.assertEqual(session.party_hybrid_state()["phase"], "RPG_TURN")
        live = session.recording()
        self.assertEqual(GameSession.from_recording(
            live, self.content, self.project).recording(), live)
        for mutate in (
            lambda cp: cp["scene_route"].update(current=CT_MISSION),
            lambda cp: cp["scene_route"].update(history=[]),
            lambda cp: cp["party_orchestration"].update(leader="missing"),
        ):
            forged = deepcopy(live)
            mutate(forged)
            forged["digest"] = digest({
                k: v for k, v in forged.items() if k != "digest"})
            with self.subTest(mutate=mutate), self.assertRaises(RuleError):
                GameSession.from_recording(forged, self.content, self.project)

    def test_unearned_ct_rewards_and_transition_rejected_after_retreat(self):
        session = GameSession.new(self.content, self.project, "main", seed=17)
        session.route_transition("village_to_woods")
        _win_rpg(session, "woods")
        session.route_transition("woods_to_crypt")
        _win_rpg(session, "crypt")
        session.route_transition("crypt_to_ct")
        _ct_step(session)
        checkpoint = session.recording()
        with self.assertRaises(RuleError):
            session.route_transition("ct_victory_to_village")
        self.assertEqual(session.recording(), checkpoint)
        session.abandon_encounter()
        with self.assertRaises(RuleError):
            session.route_transition("ct_victory_to_village")
        self.assertNotIn(CT_MISSION, session.progress.completed)
        self.assertEqual(session.progress.gold, 36)
        session.route_transition("ct_retreat_to_crypt")
        self.assertEqual(session.route_scene, "crypt")
        self.assertEqual(session.progress.gold, 36)
        self.assertEqual(GameSession.from_recording(
            session.recording(), self.content, self.project).recording(),
            session.recording())

    def test_registered_r53_creator_template_two_file_roundtrip(self):
        from drawtemp.export.templates import TEMPLATES, create_template
        from sporebound.game_project import GameProject
        from sporebound.model import Content
        self.assertIn("hybrid_r53", TEMPLATES)
        with TemporaryDirectory() as dirname:
            folder = Path(dirname) / "hybrid"
            create_template("hybrid_r53", folder)
            data = Content.load(folder / "game.json")
            project = GameProject.load(folder / "game.game.json", data)
            self.assertEqual(project.to_dict(), self.project.to_dict())
            self.assertEqual(data.to_dict(), self.content.to_dict())
            game = GameSession.new(data, project, "main", seed=17)
            self.assertEqual(game.party_hybrid_state()["phase"], "EXPLORATION")
            self.assertEqual(game.party_hybrid_state()["scene"], "village")
            self.assertEqual(game.party_orchestration_state()["leader"], "oren")

    def test_invalid_ct_scene_route_and_r53_journal_with_recomputed_digest(self):
        session = GameSession.new(self.content, self.project, "main", seed=17)
        session.route_transition("village_to_woods")
        _win_rpg(session, "woods")
        session.route_transition("woods_to_crypt")
        _win_rpg(session, "crypt")
        session.route_transition("crypt_to_ct")
        checkpoint = session.recording()
        bad = deepcopy(checkpoint)
        bad["scene_route"]["current"] = "village"
        bad["digest"] = digest({key: value for key, value in bad.items()
                                if key != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(bad, self.content, self.project)
        bad = deepcopy(checkpoint)
        bad["party_orchestration"]["formation"] = [
            "front", "front", "support"]
        bad["digest"] = digest({key: value for key, value in bad.items()
                                if key != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(bad, self.content, self.project)

    def test_player_controls_rpg_combo_routed_ct_and_checkpoint(self):
        with TemporaryDirectory() as dirname:
            folder = Path(dirname)
            player = PlayerController(self.content, self.project, "main",
                                      folder, seed=17)
            state = player.new_game()
            self.assertEqual(state["r53_hybrid"]["phase"], "EXPLORATION")
            self.assertEqual(len(state["r53_hybrid"]["members"]), 3)
            player.switch_party_leader("elya")
            self.assertTrue(player.state()["r53_hybrid"]["members"][0]["leader"])
            player.travel_route("village_to_woods")
            player.start_rpg_encounter("woods")
            before = player.state()
            self.assertEqual(before["r53_hybrid"]["phase"], "RPG_TURN")
            player.rpg_action("combo", "loup", "lames_du_relais")
            player.save(1)
            loaded = PlayerController(self.content, self.project, "main",
                                      folder, seed=17)
            loaded.load(1)
            self.assertEqual(loaded.state()["r53_hybrid"],
                             player.state()["r53_hybrid"])
            self.assertEqual(loaded.state()["rpg"], player.state()["rpg"])


if __name__ == "__main__":
    unittest.main()
