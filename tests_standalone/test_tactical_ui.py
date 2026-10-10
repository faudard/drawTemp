"""2.7 read-only tactical overlays and authoring integration regression gates."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from sporebound.authoring import upsert_job_talent, remove_job_talent
from sporebound.editor import Document
from sporebound.game_project import GameProject
from sporebound.model import Board, Content, Effect, Mission, RuleError, Skill, Unit
from sporebound.player_session import PlayerSession
from sporebound.rules import default_rules
from sporebound.tactical_rpg3 import tactical_rpg_rules
from sporebound.tactical_ui import tactical_snapshot


def sample(*, enhanced=False):
    a = Unit("hero", "Hero", "player", (2, 1), weapon="spear",
             speed=20, tags=["formation:phalanx"] if enhanced else [])
    b = Unit("friend", "Friend", "player", (2, 2), weapon="spear",
             tags=["formation:phalanx"] if enhanced else [])
    e = Unit("enemy", "Enemy", "enemy", (4, 1), speed=10)
    skill = Skill("heal", "Heal", [Effect(kind="heal", power=15)],
                  target="ally", range=3)
    return Content({"heal": skill},
                   {"arena": Mission("arena", "Arena", Board(7, 5),
                                      [a, b, e])},
                   jobs={"brave": {}})


class TacticalOverlayTests(unittest.TestCase):
    def test_snapshot_is_pure_and_bounded_to_advanced_rules(self):
        content = sample(enhanced=True)
        rules = tactical_rpg_rules()
        battle = __import__("sporebound.engine", fromlist=["Battle"]).Battle(
            content, "arena", seed=4, rules=rules)
        initial = battle.digest()
        display = tactical_snapshot(battle, (4, 1))
        self.assertTrue(display["enhanced"])
        self.assertEqual(display["selected"], [4, 1])
        self.assertEqual([x["unit"] for x in display["formations"]],
                         ["friend", "hero"])
        self.assertTrue(display["attack"])
        self.assertEqual(display, tactical_snapshot(battle, (4, 1)))
        self.assertEqual(battle.digest(), initial)
        with self.assertRaises(RuleError):
            tactical_snapshot(battle, (200, 200))
        self.assertEqual(battle.digest(), initial)

        vanilla = __import__("sporebound.engine", fromlist=["Battle"]).Battle(
            sample(), "arena", seed=4)
        original = vanilla.digest()
        overlay = tactical_snapshot(vanilla, (4, 1))
        self.assertFalse(overlay["enhanced"])
        self.assertEqual(overlay["attack"], [])
        self.assertEqual(vanilla.digest(), original)

    def test_armed_phalanx_corridor_is_visible_after_prepare(self):
        from sporebound.engine import Battle
        battle = Battle(sample(enhanced=True), "arena", seed=2,
                        rules=tactical_rpg_rules())
        battle.execute({"kind": "prepare", "mode": "phalanx_hold"})
        zones = tactical_snapshot(battle)["zones"]
        armed = [z for z in zones if z["unit"] == "hero"]
        self.assertEqual(len(armed), 1)
        self.assertTrue(armed[0]["armed"])
        self.assertIn([3, 1], armed[0]["cells"])


class TalentEditorTests(unittest.TestCase):
    def test_prerequisite_tree_crud_undo_and_invalid_cycles(self):
        doc = Document(sample())
        original = deepcopy(doc.data)
        first = upsert_job_talent(doc.data, "brave", "guard", jp=1,
                                  stat="defense", bonus=2)
        doc.replace(first)
        second = upsert_job_talent(doc.data, "brave", "banner", jp=2,
                                   requires=["guard"], skills=["heal"],
                                   exclusive="support")
        doc.replace(second)
        tree = doc.data["jobs"]["brave"]["talents"]
        self.assertEqual(tree["banner"]["requires"], ["guard"])
        self.assertEqual(tree["guard"]["bonuses"], {"defense": 2})
        with self.assertRaises(RuleError):
            remove_job_talent(doc.data, "brave", "guard")
        with self.assertRaises(RuleError):
            upsert_job_talent(doc.data, "brave", "guard",
                              requires=["banner"])
        with self.assertRaises(RuleError):
            upsert_job_talent(doc.data, "brave", "orphan",
                              requires=["missing"])
        self.assertEqual(doc.data["jobs"]["brave"]["talents"], tree)
        doc.undo()
        self.assertNotIn("banner", doc.data["jobs"]["brave"]["talents"])
        doc.undo()
        self.assertEqual(doc.data, original)
        doc.redo()
        without_guard = remove_job_talent(
            doc.data, "brave", "guard")
        self.assertEqual(without_guard["jobs"]["brave"]["talents"], {})


class PlayerIntegrationTests(unittest.TestCase):
    def test_authored_tactical_roles_enable_rules_on_player_mission_only(self):
        for advanced in (False, True):
            with self.subTest(advanced=advanced):
                content = sample(enhanced=advanced)
                if advanced:
                    content.missions["arena"].units[2].tags = ["protector"]
                project = GameProject.default(content)
                with TemporaryDirectory() as folder:
                    session = PlayerSession(content, project,
                                            Path(folder) / "profile.json")
                    session.new_game("main", 1)
                    session.begin("arena")
                    self.assertEqual(
                        "formation" in session.battle.rules.commands,
                        advanced)
                    if not advanced:
                        self.assertEqual(session.battle.rules.manifest(),
                                         default_rules().manifest())
                    else:
                        snapshot = tactical_snapshot(session.battle)
                        self.assertTrue(snapshot["enhanced"])
                        self.assertTrue(snapshot["formations"])


if __name__ == "__main__":
    unittest.main()
