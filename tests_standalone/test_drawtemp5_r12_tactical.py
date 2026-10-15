"""R12.5/6 tactical HUD: engine projections, non-RNG previews, resume gate."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.controller import PlayerController
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.sdk.simulation import SimulationError, thaw
from sporebound.ai import choose_command
from sporebound.presentation import battle_frame
from sporebound.tactical_intents import tactical_intents


class TacticalPlayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        content, project = reference_project()
        self.game = PlayerController(content, project, "main", self.tmp.name)
        self.game.new_game()
        self.game.choose("enter")
        self.game.start_mission(MISSION)
        self.assertIn(self.game.state()["screen"], ("battle", "result"))

    def test_projection_is_immutable_replay_safe_and_revision_checked(self):
        sim = self.game.session
        snap = sim.snapshot()
        original = sim.recording()
        cell = [0, 0]
        first = sim.tactical_presentation(cell, expected_revision=snap.revision)
        self.assertEqual(first["source_revision"], snap.revision)
        self.assertEqual(sim.recording(), original)
        self.assertEqual(sim.snapshot(), snap)
        self.assertEqual(first, sim.tactical_presentation(cell))
        with self.assertRaises(TypeError):
            first["source_revision"] = 900
        with self.assertRaises(TypeError):
            first["focus"]["can_target"] = True
        with self.assertRaises(SimulationError) as exc:
            sim.tactical_presentation(cell, expected_revision=snap.revision + 1)
        self.assertEqual(exc.exception.code, "stale_revision")
        self.assertEqual(sim.recording(), original)

    def test_timeline_danger_and_hud_derived_from_shared_engine(self):
        sim = self.game.session
        battle = sim._session.active_battle
        frame = battle_frame(battle, selected=(0, 0), skill="attack")
        expected = tactical_intents(battle)
        visual = thaw(sim.tactical_presentation([0, 0]))
        self.assertEqual(visual["timeline"], expected["timeline"])
        self.assertEqual(visual["danger"], expected["danger"])
        self.assertEqual(visual["casts"], expected["casts"])
        self.assertEqual(visual["charges"], expected["charges"])
        self.assertEqual(visual["headline"], (
            "Combat terminé : " + frame.result if frame.result else
            "Déploiement" if frame.deploying else
            "Tour actif : " + str(frame.active_id or "ordonnancement")))
        self.assertEqual(visual["objective"], battle.mission.objective)
        self.assertEqual(len(visual["roster"]), len(battle.units))
        self.assertTrue(all(row["certainty"] in
                            ("certain", "scheduled", "armed", "possible")
                            for row in visual["danger"]))

    def test_invalid_cells_and_skill_ids_leave_game_unchanged(self):
        sim = self.game.session
        before = sim.recording()
        for cell in ([-1, 0], [0, 99999], [True, 0], ["1", 0], [0], 0):
            with self.subTest(cell=cell), self.assertRaises(ValueError):
                sim.tactical_presentation(cell)
        for skill in ("", 1, "x" * 100):
            with self.subTest(skill=skill), self.assertRaises(ValueError):
                sim.tactical_presentation([0, 0], skill)
        self.assertEqual(sim.recording(), before)

    def test_forecast_matches_canonical_rules_not_sampled_damage(self):
        sim = self.game.session
        for _ in range(100):
            battle = sim._session.active_battle
            if battle.result:
                self.skipTest("encounter ended before player activation")
            if battle.deploying:
                sim.execute({"kind": "start_battle"})
            elif battle.active is not None and battle.active.team == "enemy":
                sim.auto_enemy_turn()
            else:
                break
        battle = sim._session.active_battle
        if battle.active is None or battle.active.team != "player":
            self.skipTest("no player activation available")
        target = next((u for u in battle.units if u.team == "enemy" and u.alive),
                      battle.active)
        original = sim.recording()
        visual = thaw(sim.tactical_presentation(list(target.pos), "attack"))
        self.assertEqual(visual["active"]["id"], battle.active.id)
        self.assertEqual(visual["focus"]["line_of_sight"],
                         battle.line_of_sight(battle.active.pos, target.pos))
        try:
            forecast = battle.forecast("attack", target.pos, battle.active)
        except ValueError as exc:
            self.assertFalse(visual["focus"]["can_target"])
            self.assertEqual(visual["focus"]["error"], str(exc))
        else:
            self.assertTrue(visual["focus"]["can_target"])
            self.assertEqual(visual["focus"]["forecast"], forecast)
        self.assertEqual(sim.recording(), original)

        self.game.select_cell(*target.pos)
        rev = self.game.state()["revision"]
        if visual["focus"]["can_target"]:
            self.assertIn("Prévision (non garantie)", self.game.preview("attack")["forecast"])
        else:
            with self.assertRaises(ValueError):
                self.game.preview("attack")
        self.assertEqual(rev, self.game.state()["revision"])
        self.assertEqual(sim.recording(), original)

    def test_reachable_cost_and_risk_use_engine_path(self):
        sim = self.game.session
        for _ in range(100):
            battle = sim._session.active_battle
            if battle.deploying:
                sim.execute({"kind": "start_battle"})
            elif battle.result or battle.active is None:
                self.skipTest("battle ended before player activation")
            elif battle.active.team == "enemy":
                sim.auto_enemy_turn()
            else:
                break
        battle = sim._session.active_battle
        if battle.active.team != "player":
            self.skipTest("no player activation")
        targets = {point: move for point, move in battle.reachable().items()
                   if point != battle.active.pos}
        if not targets:
            self.skipTest("no legal move available")
        cell = sorted(targets)[0]
        cost, path = targets[cell]
        initial = sim.recording()
        view = thaw(sim.tactical_presentation(list(cell)))
        self.assertIn(list(cell), view["reachable"])
        self.assertEqual(view["focus"]["move"]["cost"], cost)
        self.assertEqual(view["focus"]["move"]["path"], [list(p) for p in path])
        self.assertEqual(view["focus"]["move"]["risks"],
                         battle.movement_threats(battle.active, path))
        self.game.select_cell(*cell)
        self.assertIn("Déplacement", self.game.preview("move")["forecast"])
        self.assertEqual(sim.recording(), initial)

    def test_reference_battle_result_and_save_resume_without_studio(self):
        # A test-only autopilot drives the existing deterministic AI policy.
        # No Player code auto-decides human actions.
        game = self.game
        game.interact_object("lever")
        for _ in range(700):
            battle = game.session._session.active_battle
            if battle.result:
                break
            game.session.execute(choose_command(battle))
        self.assertEqual(game.session.snapshot().battle["result"], "victory")
        self.assertEqual(game.state()["screen"], "result")
        before = game.session.recording()
        game.save(1)
        saved = Path(self.tmp.name) / "slot_1.json"
        disk = saved.read_bytes()
        clone = PlayerController(game.content, game.project, "main", self.tmp.name)
        self.assertEqual(clone.load(1)["screen"], "result")
        self.assertEqual(clone.session.recording(), before)
        self.assertEqual(saved.read_bytes(), disk)
        self.assertEqual(clone.finish_battle()["screen"], "campaign")
        self.assertEqual(clone.session.snapshot().mode, "campaign")


if __name__ == "__main__":
    unittest.main()
