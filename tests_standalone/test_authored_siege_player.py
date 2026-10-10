"""2.8.2 — Any Studio blueprint can resume in Player with real side battles."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import unittest

from examples.siege_fronts import siege_session
from examples.siege_scenarios import siege_content
from sporebound.authored_siege_player import AuthoredSiegeController, active_side_encounter
from sporebound.game_project import GameProject
from sporebound.model import RuleError
from sporebound import siege_authoring as edit


def siege_blueprint():
    template = siege_session(contested=True, decisions=True, campaign=True, paths=True)
    return {"id": "studio_castle", "campaign_id": "main",
            "fronts": dict(template.missions), "focused": template.initial_focus,
            "specs": deepcopy(template.initial_specs),
            "links": deepcopy(template.links),
            "campaign": deepcopy(template.initial_campaign),
            "logistics": deepcopy(template.initial_logistics)}


class AuthoredSiegePlayerTests(unittest.TestCase):
    def simple(self):
        content = siege_content()
        bp = edit.new_blueprint("custom", "main", "castle_ram", front="gate")
        bp = edit.add_front(bp, "walls", "castle_ramparts")
        return content, bp

    def test_existing_254_projects_are_compatible_and_replayable(self):
        content, bp = self.simple()
        project = edit.replace_siege(GameProject.default(content), content, bp)
        self.assertEqual(project.sieges[0], bp)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "project.game.json"
            a = AuthoredSiegeController(content, bp, path, 2)
            a.new_game(seed=14)
            a.execute({"kind": "start_battle"})
            a.doctrine("walls", "assault")
            a.advance()
            b = AuthoredSiegeController(content, bp, path, 2)
            b.continue_game()
            self.assertEqual(a.session.fronts.digest(), b.session.fronts.digest())
            self.assertEqual(a.session.fronts.history, b.session.fronts.history)
            self.assertNotIn("logistics", bp)
            with self.assertRaises(RuleError):
                a.new_game(seed=15)
            other = deepcopy(bp)
            other["specs"]["walls"]["strength"] = 9
            with self.assertRaises(RuleError):
                AuthoredSiegeController(content, other, path, 2).continue_game()

    def test_failed_commands_and_writes_roll_back_exactly(self):
        content, bp = self.simple()
        with TemporaryDirectory() as folder:
            a = AuthoredSiegeController(content, bp,
                                        Path(folder) / "project.game.json", 1)
            a.new_game()
            before = a.session.fronts.recording()
            with self.assertRaises(RuleError):
                a.switch("not_a_front")
            self.assertEqual(before, a.session.fronts.recording())
            with patch.object(a, "save", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    a.advance()
            self.assertEqual(before, a.session.fronts.recording())
            b = AuthoredSiegeController(content, bp,
                                        Path(folder) / "project.game.json", 1)
            self.assertEqual(b.continue_game().fronts.recording(), before)

    def test_authored_logistics_opt_in_validates_and_replays(self):
        content = siege_content()
        bp = siege_blueprint()
        project = edit.replace_siege(GameProject.default(content), content, bp)
        self.assertEqual(project.sieges[0]["logistics"]["escorts"], 1)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "castle.game.json"
            project.save(path, content)
            reread = GameProject.load(path, content)
            self.assertEqual(reread.sieges[0], bp)
            a = AuthoredSiegeController(content, bp, path, 1)
            a.new_game(seed=3)
            self.assertEqual(a.session.fronts.logistics.reserves["player"], 3)
            a.route("direct")
            a.advance()
            b = AuthoredSiegeController(content, bp, path, 1)
            b.continue_game()
            self.assertEqual(b.session.fronts.digest(), a.session.fronts.digest())
            changed = deepcopy(bp)
            changed["logistics"]["supplies"]["player"] += 1
            with self.assertRaises(RuleError):
                AuthoredSiegeController(content, changed, path).continue_game()
            bad = deepcopy(bp)
            bad["logistics"]["ambushes"][0]["from"] = "missing"
            with self.assertRaises(RuleError):
                edit.replace_siege(project, content, bad)

    def test_counteroffensive_routes_real_side_battle_to_journal(self):
        content = siege_content()
        bp = siege_blueprint()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "castle.game.json"
            ctrl = AuthoredSiegeController(content, bp, path, 1)
            ctrl.new_game(seed=3)
            ctrl.doctrine("gate", "assault")
            for _ in range(5):
                ctrl.advance()
            side = ctrl.active_encounter()
            self.assertIsNotNone(side)
            self.assertEqual(side[0], "recovery")
            self.assertEqual(side[1], "gate")
            self.assertIs(ctrl.current_battle(), side[2])
            with self.assertRaises(RuleError):
                ctrl.switch("gate")
            command = ({"kind": "start_battle"} if side[2].deploying
                       else {"kind": "end"})
            ctrl.execute(command)
            self.assertIn("execute_recovery",
                          [h["kind"] for h in ctrl.session.fronts.history])
            resumed = AuthoredSiegeController(content, bp, path, 1)
            resumed.continue_game()
            self.assertEqual(resumed.active_encounter()[0], "recovery")
            self.assertEqual(resumed.session.fronts.digest(),
                             ctrl.session.fronts.digest())
            ctrl.abandon_side()
            self.assertIsNone(ctrl.active_encounter())
            self.assertEqual(resumed.session.fronts.history[-1]["kind"],
                             "execute_recovery")

    def test_tampered_checkpoint_cannot_be_resumed(self):
        content, bp = self.simple()
        with TemporaryDirectory() as folder:
            a = AuthoredSiegeController(content, bp,
                                        Path(folder) / "project.game.json", 1)
            a.new_game()
            path = a.save_path
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["recording"]["operations"].append({"kind": "advance"})
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(RuleError):
                AuthoredSiegeController(content, bp,
                                        a.project_path, 1).continue_game()


if __name__ == "__main__":
    unittest.main()
