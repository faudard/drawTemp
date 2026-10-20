"""R31.H reference Jeanne journey: Studio -> real Player -> verified saves.

No fake combat outcomes, private Battle mutation, ad-hoc JSON edits, mock
dispatch or alternate Player controller. All player commands are revision
checked and go through the existing native Simulation/GameSession runtime.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringSession, AuthoringError
from drawtemp.sdk.logic_graph import LogicGraphError, graphs_from_project
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.logic_vertical_slice import (
    GRAPH, FLAG, QUEST, CHEST, OBJECTIVE, REWARD_SCENE,
    CHEST_LOOT, STORY_REWARD, preview_reference_quest,
    install_reference_quest,
)
from drawtemp.player.qt_app import build_controller
from sporebound.game_session import GameSession
from sporebound.logic_variables import variables_from_journal
from sporebound.logic_campaign_bridge import EXTENSION


def author(folder):
    content, project = reference_project()
    studio = AuthoringSession.new(content, project)
    plan = preview_reference_quest(studio)
    assert not studio.snapshot().dirty
    studio.apply(plan)
    path = Path(folder) / "jeanne-r31h.json"
    studio.save_as(path)
    return path, studio


def player(folder, path):
    return build_controller(content_path=path,
                            save_dir=Path(folder) / "saves",
                            campaign_id="main")


def player_jeanne_turn(game, *, budget=40):
    for _ in range(budget):
        state = game.state()
        battle = state["battle"]
        if not battle or battle["result"]:
            raise AssertionError("Battle finished before player action")
        active = battle["active"]
        if active == "jeanne":
            return battle
        if active == "renaud_mentor":
            game.advance_enemy(limit=8)
        else:
            raise AssertionError("Unexpected active actor: " + str(active))
    raise AssertionError("Timed out awaiting authentic Jeanne activation")


def defeat_mentor(game):
    """Run a genuine attack with an accessible target; do not mutate enemy HP."""
    for _ in range(30):
        battle = player_jeanne_turn(game)
        enemy = next((row for row in battle["units"]
                      if row["id"] == "renaud_mentor"), None)
        if enemy is None or enemy["hp"] <= 0:
            return
        hero = next(row for row in battle["units"] if row["id"] == "jeanne")
        if abs(hero["pos"][0] - enemy["pos"][0]) + abs(
                hero["pos"][1] - enemy["pos"][1]) > 1:
            # Native CT movement and reachable cells, not teleport.
            adjacent = [(enemy["pos"][0] - 1, enemy["pos"][1]),
                        (enemy["pos"][0], enemy["pos"][1] - 1)]
            for pos in adjacent:
                if pos == (3, 4):
                    game.select_cell(*pos)
                    game.command("move")
                    break
        game.select_cell(*enemy["pos"])
        game.command("attack")
        battle = game.state()["battle"]
        if not any(row["id"] == "renaud_mentor" and row["hp"] > 0
                   for row in battle["units"]):
            return
        game.command("end")
    raise AssertionError("Real R9 combat did not defeat mentor within budget")


class ReferenceJourneyTests(unittest.TestCase):
    def test_one_r1_preview_creates_canonical_quest_with_single_undo(self):
        content, project = reference_project()
        studio = AuthoringSession.new(content, project)
        before = studio.snapshot().to_dict()
        plan = preview_reference_quest(studio)
        self.assertEqual(studio.snapshot().to_dict(), before)
        studio.apply(plan)
        after = studio.snapshot().to_dict()
        self.assertEqual(studio.revision, 1)
        self.assertNotEqual(after, before)
        mission = next(x for x in after["content"]["missions"]
                       if x["id"] == MISSION)
        self.assertEqual(mission["objective"], OBJECTIVE)
        self.assertEqual([tuple(cell) for cell in mission["goal"]], [(6, 4)])
        chest = next(x for x in mission["objects"] if x["id"] == CHEST)
        self.assertEqual(chest["amount"], CHEST_LOOT)
        self.assertEqual(len([g for g in graphs_from_project(after["project"])
                              if g["id"] == GRAPH]), 1)
        self.assertEqual(
            after["project"]["extensions"][EXTENSION]["data"]["bindings"][0]
            ["target"], FLAG)
        self.assertEqual(after["project"]["story"]["after_mission"][MISSION],
                         REWARD_SCENE)
        studio.undo()
        self.assertEqual(studio.snapshot().to_dict()["content"],
                         before["content"])
        self.assertEqual(studio.snapshot().to_dict()["project"],
                         before["project"])
        studio.redo()
        self.assertEqual(studio.snapshot().to_dict()["content"],
                         after["content"])

    def test_rejected_user_customizations_never_mutate_reference(self):
        content, project = reference_project()
        data = content.to_dict()
        data["missions"][0]["name"] = "Autre mission"
        original = deepcopy(data)
        studio = AuthoringSession.new(data, project)
        with self.assertRaises(LogicGraphError):
            preview_reference_quest(studio)
        self.assertEqual(studio.snapshot().to_dict()["content"], original)
        self.assertEqual(studio.revision, 0)
        _, original_project = reference_project()
        other = original_project.to_dict()
        other["story"]["scenes"][0]["text"] = "Un récit différent"
        studio = AuthoringSession.new(content, other)
        with self.assertRaises(LogicGraphError):
            preview_reference_quest(studio)
        self.assertEqual(studio.revision, 0)

    def test_repeated_install_and_stale_preview_fail_closed(self):
        content, project = reference_project()
        session = AuthoringSession.new(content, project)
        plan = preview_reference_quest(session)
        session.apply(plan)
        before = session.snapshot().to_dict()
        with self.assertRaises((LogicGraphError, AuthoringError)):
            install_reference_quest(session)
        with self.assertRaises(AuthoringError):
            session.apply(plan)
        self.assertEqual(session.snapshot().to_dict(), before)

    def test_player_npc_locked_gate_real_combat_chest_quest_and_resume(self):
        with TemporaryDirectory() as folder:
            path, studio = author(folder)
            self.assertTrue(path.exists())
            self.assertTrue(path.with_suffix(".game.json").exists())
            self.assertEqual(
                AuthoringSession.open(path).snapshot().to_dict()["content"],
                studio.snapshot().to_dict()["content"])
            game = player(folder, path)
            self.assertEqual(game.new_game()["screen"], "dialogue")
            self.assertEqual(game.state()["scene"]["id"], "arrival")
            game.choose("enter")
            self.assertIs(game.session.snapshot().progress["story_flags"]
                          ["r31_npc_spoken"], True)
            game.start_mission(MISSION)
            battle = player_jeanne_turn(game)
            self.assertFalse(next(x for x in battle["objects"]
                                  if x["id"] == "gate").get("open", False))
            self.assertFalse(next(x for x in battle["objects"]
                                  if x["id"] == CHEST).get("used", False))
            # Real native interaction: the lever opens the formerly blocked gate.
            game.interact_object("lever")
            self.assertTrue(next(x for x in game.state()["battle"]["objects"]
                                 if x["id"] == "gate")["open"])
            game.command("end")
            player_jeanne_turn(game)
            game.select_cell(3, 4)
            game.command("move")
            defeat_mentor(game)
            self.assertFalse(game.state()["battle"]["result"])
            # Movement was spent approaching the mentor: next CT turn first.
            game.command("end")
            player_jeanne_turn(game)
            game.select_cell(4, 4)
            game.command("move")
            game.interact_object(CHEST)
            battle = game.state()["battle"]
            self.assertTrue(next(x for x in battle["objects"]
                                 if x["id"] == CHEST)["used"])
            game.save(1)
            file = Path(folder) / "saves" / "slot_1.json"
            checkpoint = file.read_bytes()
            # Primary slot verification (checks checksum, project, rules and
            # canonical replay) must precede any test of the tactical journal.
            inspected = game._store(1).inspect()
            self.assertEqual(inspected.primary, "valid")
            verified_slot = game._store(1).load()
            self.assertEqual(verified_slot.recording(), game.session.recording())
            replayed = GameSession.from_recording(
                verified_slot.recording(), game.content, game.project)
            self.assertEqual(replayed.active_battle.loot, CHEST_LOOT)
            self.assertEqual(variables_from_journal(replayed.active_battle),
                             {FLAG: True})
            self.assertEqual(sum(row["kind"] == "interact" and row.get("object") == CHEST
                                 for row in replayed.active_battle.events), 1)
            self.assertIsNone(replayed.progress.story_flags.get(FLAG))
            resumed = player(folder, path)
            resumed.load(1)
            self.assertEqual(file.read_bytes(), checkpoint)
            self.assertEqual(resumed.state()["battle"], battle)
            # The real objective requires the chest AND the defeated enemy.
            resumed.command("end")
            player_jeanne_turn(resumed)
            resumed.select_cell(6, 4)
            resumed.command("move")
            outcome = resumed.state()["battle"]
            self.assertEqual(outcome["result"], "victory")
            resumed.finish_battle()
            self.assertEqual(resumed.state()["screen"], "dialogue")
            self.assertEqual(resumed.state()["scene"]["id"], REWARD_SCENE)
            self.assertIn("claim", [c["id"] for c in resumed.state()["choices"]])
            resumed.choose("claim")
            final = resumed.session.snapshot().progress
            self.assertIs(final["story_flags"][FLAG], True)
            self.assertIs(final["story_flags"][QUEST], True)
            self.assertIn(MISSION, final["completed"])
            self.assertGreaterEqual(final["gold"], CHEST_LOOT + STORY_REWARD)
            resumed.save(1)
            last = file.read_bytes()
            again = player(folder, path)
            again.load(1)
            self.assertEqual(again.session.snapshot().progress, final)
            self.assertEqual(file.read_bytes(), last)
            checkpoint_slot = again._store(1)
            self.assertEqual(checkpoint_slot.inspect().primary, "valid")
            checkpoint_game = GameSession.from_recording(
                checkpoint_slot.load().recording(), game.content, game.project)
            self.assertEqual(len(checkpoint_game.progress.story_history), 2)

    def test_tampered_player_slot_fails_without_switching_live_state(self):
        import json
        with TemporaryDirectory() as folder:
            path, _ = author(folder)
            game = player(folder, path)
            game.new_game()
            game.choose("enter")
            game.start_mission(MISSION)
            game.save(1)
            before = game.session.recording()
            file = Path(folder) / "saves" / "slot_1.json"
            save = json.loads(file.read_text(encoding="utf-8"))
            self.assertEqual(save["kind"], "game_session")
            save["digest"] = "0" * 64
            file.write_text(json.dumps(save), encoding="utf-8")
            from drawtemp.sdk.simulation import SimulationError
            with self.assertRaises(SimulationError) as raised:
                game.load(1)
            self.assertEqual(raised.exception.code, "invalid_save")
            self.assertEqual(game.session.recording(), before)
            self.assertEqual(json.loads(file.read_text())["digest"], "0" * 64)
            self.assertEqual(game._store(1).inspect().primary, "invalid")

    def test_invalid_quest_objective_cannot_lose_its_chest_contract(self):
        from sporebound.model import Content, RuleError
        with TemporaryDirectory() as folder:
            path, session = author(folder)
            authored = session.snapshot().to_dict()["content"]
            mission = next(row for row in authored["missions"]
                           if row["id"] == MISSION)
            bad = deepcopy(authored)
            target = next(row for row in bad["missions"]
                          if row["id"] == MISSION)
            target["objects"] = [row for row in target["objects"]
                                  if row["id"] != CHEST]
            with self.assertRaises(RuleError):
                Content.from_dict(bad)
            bad = deepcopy(authored)
            target = next(row for row in bad["missions"]
                          if row["id"] == MISSION)
            next(row for row in target["objects"]
                 if row["id"] == CHEST)["used"] = True
            with self.assertRaises(RuleError):
                Content.from_dict(bad)
            self.assertEqual(
                next(row for row in mission["objects"]
                     if row["id"] == CHEST).get("used", False), False)

    def test_objective_rejects_shortcut_to_exit_without_loot(self):
        from sporebound.engine import Battle
        from sporebound.logic_vertical_objective import achieved
        with TemporaryDirectory() as folder:
            path, _ = author(folder)
            game = player(folder, path)
            game.new_game()
            game.choose("enter")
            game.start_mission(MISSION)
            # Pure native objective remains unsatisfied before actual play.
            mission = game.content.missions[MISSION]
            self.assertEqual(mission.objective, OBJECTIVE)
            real = Battle(game.content, MISSION, seed=13)
            self.assertFalse(achieved(real))
            self.assertFalse(real.result == "victory")


if __name__ == "__main__":
    unittest.main()
