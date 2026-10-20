"""R37.E regression: R6 boss phases, telegraphs, authoring, replay and legacy."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.studio.ai_boss_authoring import BossDirectorDesigner
from sporebound.advanced_ai import EXTENSION
from sporebound.ai_boss_director import (
    preview_boss_director, validate_boss_directors)
from sporebound.engine import Battle
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import RuleError
from sporebound.tactical_r6 import tactical_r6_rules
from tests_standalone.test_elite_boss_r6 import encounter


def fixture(*, with_director=True):
    """R6 phase 2→3 transition and a real queue_wave trigger, not a new engine."""
    content = encounter(hero=(6, 3), boss=(1, 1), phase=2,
                        triggers=[{
                            "id": "final_fury", "condition": "hp_below",
                            "unit": "warden", "percent": 60,
                            "actions": [
                                {"kind": "boss_phase", "unit": "warden",
                                 "phase": 3,
                                 "bonuses": {"defense": 2}},
                                {"kind": "queue_wave", "actors": [
                                    {"id": "reserve", "name": "Reserve",
                                     "team": "enemy", "pos": [8, 6]},
                                ]},
                            ],
                        }])
    project = GameProject.default(content)
    data = {"version": 1, "agents": [{
        "id": "warden", "mode": "ct",
        "policies": [{"id": "wait", "action": "wait",
                      "base": 0, "when": {}, "terms": {}}],
    }]}
    director = {
        "id": "throne_warden", "mission": "throne", "boss": "warden",
        "phases": [
            {"phase": 2, "label": "Warden", "cue": "Watch the approach",
             "trigger": None},
            {"phase": 3, "label": "Fury", "cue": "The guard calls reinforcements",
             "trigger": "final_fury"},
        ],
    }
    if with_director:
        data["boss_directors"] = [director]
    project.extensions[EXTENSION] = {
        "schema_version": 1, "data": data, "references": []}
    project.validate(content)
    return content, project, director


class R37BossDirectorTests(unittest.TestCase):
    def test_strict_existing_phase_and_trigger_validation(self):
        content, project, director = fixture()
        self.assertEqual(
            validate_boss_directors([director], content=content),
            [director])
        cases = [
            lambda row: row.update(id="../hack"),
            lambda row: row.update(mission="unknown"),
            lambda row: row.update(boss="hero"),
            lambda row: row["phases"][0].update(trigger="final_fury"),
            lambda row: row["phases"][1].update(trigger="ghost"),
            lambda row: row["phases"][1].update(phase=4),
            lambda row: row["phases"][1].update(label=""),
            lambda row: row["phases"][1].update(cue="x" * 161),
            lambda row: row["phases"][1].update({"script": "execute()"}),
            lambda row: row["phases"].pop(),
        ]
        for mutate in cases:
            candidate = deepcopy(director)
            mutate(candidate)
            with self.subTest(mutate=mutate), self.assertRaises(RuleError):
                validate_boss_directors([candidate], content=content)
        with self.assertRaises(RuleError):
            validate_boss_directors([director, director], content=content)
        p = deepcopy(project)
        p.extensions[EXTENSION]["data"]["boss_directors"][0][
            "phases"][1]["trigger"] = "ghost"
        with self.assertRaises(RuleError):
            p.validate(content)

    def test_real_ct_preview_does_not_execute_commands_or_fabricate_waves(self):
        content, project, director = fixture()
        rules = tactical_r6_rules()
        battle = Battle(content, "throne", rules=rules, seed=17)
        before = battle.digest()
        view = preview_boss_director(battle, director)
        self.assertEqual(view["id"], "throne_warden")
        self.assertEqual(view["current_phase"], 2)
        self.assertEqual(view["current_label"], "Warden")
        self.assertEqual(view["phases"][1]["hp_gate_percent"], 60)
        self.assertEqual(view["phases"][1]["status"], "possible")
        self.assertTrue(view["preview_only"])
        self.assertFalse(view["queued_waves"])
        self.assertFalse(view["arrived_reinforcements"])
        self.assertTrue(view["possible_reinforcements"])
        self.assertEqual(view["telegraph"]["certainty"], "unknown")
        self.assertIsNone(view["telegraph"]["command"])
        self.assertEqual(view, preview_boss_director(battle, director))
        self.assertEqual(battle.digest(), before)
        # Use actual legal End commands so the tactical replay remains valid.
        for _ in range(3):
            if battle.result:
                break
            battle.execute({"kind": "end"})
        self.assertEqual(battle.digest(),
                         Battle.replay(battle.recording(), rules=rules).digest())
        self.assertEqual(preview_boss_director(
            battle, director)["current_phase"], 2)

    def test_session_preview_save_and_unconfigured_legacy(self):
        content, project, director = fixture()
        rules = tactical_r6_rules()
        game = GameSession.new(content, project, "main", rules=rules, seed=23)
        with self.assertRaises(RuleError):
            game.ai_boss_preview(director["id"])
        game.start_mission("throne")
        checkpoint = game.recording()
        view = game.ai_boss_preview(director["id"])
        self.assertEqual(view["boss"], "warden")
        self.assertEqual(view["phases"][1]["trigger"], "final_fury")
        self.assertEqual(game.recording(), checkpoint)
        with self.assertRaises(RuleError):
            game.ai_boss_preview("unknown_director")
        with TemporaryDirectory() as directory:
            path = Path(directory) / "director.json"
            game.save(path)
            resumed = GameSession.load(path, content, project, rules=rules)
        self.assertEqual(resumed.recording(), checkpoint)
        self.assertEqual(resumed.ai_boss_preview(director["id"]), view)
        legacy = deepcopy(project)
        legacy.extensions.pop(EXTENSION)
        plain = GameSession.new(content, legacy, "main", rules=rules)
        self.assertNotIn("advanced_ai", plain.recording())
        with self.assertRaises(RuleError):
            plain.ai_boss_preview(director["id"])

    def test_studio_suggest_edit_undo_redo_and_stale_preview(self):
        content, project, director = fixture(with_director=False)
        author = AuthoringSession.new(content, project)
        designer = BossDirectorDesigner(author)
        self.assertEqual(designer.catalog(), [])
        self.assertEqual(designer.choices(), [
            {"mission": "throne", "boss": "warden"}])
        proposed = designer.suggest("throne", "warden")
        self.assertEqual([row["phase"] for row in proposed["phases"]], [2, 3])
        self.assertEqual(proposed["phases"][1]["trigger"], "final_fury")
        plan = designer.preview_add(
            "throne", "warden", expected_revision=author.revision)
        self.assertEqual(author.revision, 0)
        designer.apply(plan)
        self.assertEqual(author.revision, 1)
        self.assertEqual(len(designer.catalog()), 1)
        with self.assertRaises(AuthoringError):
            designer.apply(plan)
        key = designer.catalog()[0]["id"]
        edited = designer.preview_phase(
            key, 3, label="Fury Unbound", cue="Danger on the flanks",
            expected_revision=author.revision)
        designer.apply(edited)
        self.assertEqual(designer.catalog()[0]["phases"][1]["label"],
                         "Fury Unbound")
        author.undo()
        self.assertEqual(designer.catalog()[0]["phases"][1]["label"],
                         "Phase 3")
        author.redo()
        self.assertEqual(designer.catalog()[0]["phases"][1]["label"],
                         "Fury Unbound")
        with self.assertRaises(ValueError):
            designer.preview_remove(key, expected_revision=0)
        removal = designer.preview_remove(key)
        designer.apply(removal)
        self.assertEqual(designer.catalog(), [])
        author.undo()
        self.assertEqual(designer.catalog()[0]["id"], key)

    def test_reject_fake_scripted_transition_or_unsupported_actor(self):
        content, project, director = fixture()
        forged = deepcopy(content)
        mission = forged.missions["throne"]
        mission.triggers[0]["actions"][0]["phase"] = 4
        with self.assertRaises(RuleError):
            validate_boss_directors([director], content=forged)
        forged = deepcopy(content)
        mission = forged.missions["throne"]
        mission.triggers[0]["condition"] = "tick"
        mission.triggers[0].pop("percent")
        mission.triggers[0]["value"] = 10
        with self.assertRaises(RuleError):
            validate_boss_directors([director], content=forged)
        forged = deepcopy(content)
        forged.missions["throne"].units[1].behavior = "tactical"
        with self.assertRaises(RuleError):
            validate_boss_directors([director], content=forged)


if __name__ == "__main__":
    unittest.main()
