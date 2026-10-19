"""R25.B: canonical village -> tactical scene transitions, save and replay."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.reference import MISSION, reference_project
from sporebound.ai import choose_command
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError


def scene_fixture():
    content, project = reference_project()
    project.story["entry_scenes"] = {}  # Explicit route entry, no intro gate.
    project.exploration["arrival"] = {
        "title": "Village", "theme": "village",
        "width": 4, "height": 4, "start": [0, 1],
        "blocked": [[2, 1]],
        "interactions": [{
            "id": "exit", "title": "Route", "text": "Vers la bataille",
            "pos": [1, 2], "required": False, "exit": True,
        }],
    }
    hero = next(u for u in content.missions[MISSION].units
                if u.team == "player")
    project.game_modes = {
        "version": 1, "default": {"preset": "srpg"},
        "scenes": {
            "arrival": {"preset": "action"},
            MISSION: {"preset": "srpg"},
        },
    }
    project.scene_routes = {
        "version": 1, "start": "arrival",
        "links": [
            {
                "id": "to_arena", "source": "arrival",
                "destination": MISSION, "spawn": list(hero.pos),
                "when": {"flag": "portal_open", "eq": True},
            },
            {
                "id": "retreat", "source": MISSION,
                "destination": "arrival", "spawn": [1, 1],
            },
            {
                "id": "victory_return", "source": MISSION,
                "destination": "arrival", "spawn": [1, 1],
                "when": {"completed_mission": MISSION},
            },
        ],
    }
    project.validate(content)
    return content, project


class R25SceneRouterTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = scene_fixture()
        self.session = GameSession.new(
            self.content, self.project, "main", seed=17)

    def test_legacy_jeanne_format_stays_unchanged(self):
        content, old_project = reference_project()
        self.assertNotIn("scene_routes", old_project.to_dict())
        session = GameSession.new(content, old_project, "main", seed=17)
        old = session.recording()
        self.assertNotIn("scene_route", old)
        self.assertNotIn("scene_routes", session.project.to_dict())
        self.assertEqual(GameSession.from_recording(
            old, content, old_project).recording(), old)

    def test_project_routes_roundtrip_and_resolved_profiles(self):
        document = self.project.to_dict()
        self.assertIn("scene_routes", document)
        self.assertEqual(GameProject.from_dict(
            json.loads(json.dumps(document)),
            self.content).to_dict(), document)
        self.assertEqual(self.session.route_scene, "arrival")
        self.assertEqual(self.session.scene_profile("arrival")["combat"],
                         "ACTION_REALTIME")
        self.assertEqual(self.session.scene_profile(MISSION)["combat"],
                         "TACTICAL_CT")

    def test_transitions_retain_inventory_flags_and_actual_ct_replay(self):
        session = self.session
        session.progress.story_flags["portal_open"] = True
        session.progress.story_flags["quest_found"] = True
        session.progress.inventory["potion"] = 3
        session.progress.hero("jeanne").xp = 12
        self.assertEqual(session.route_state()["position"], [0, 1])
        self.assertEqual(session.route_move(1, 0)["position"], [1, 1])
        result = session.route_transition("to_arena")
        self.assertEqual(result["scene"], MISSION)
        self.assertEqual(result["mode"], "battle")
        self.assertEqual(session.mode, "battle")
        self.assertEqual(session.active_battle.mission.id, MISSION)
        self.assertEqual(session.route_history, ["to_arena"])
        with self.assertRaises(RuleError):
            session.route_transition("retreat")
        session.execute({"kind": "interact", "unit": "jeanne", "object": "lever"})
        with TemporaryDirectory() as temp:
            path = Path(temp) / "route-session.json"
            session.save(path)
            restored = GameSession.load(path, self.content, self.project)
            self.assertEqual(restored.recording(), session.recording())
            self.assertEqual(restored.active_battle.digest(),
                             session.active_battle.digest())
            self.assertEqual(restored.route_scene, MISSION)
            self.assertEqual(restored.progress.inventory["potion"], 3)
            self.assertTrue(restored.progress.story_flags["quest_found"])
            self.assertEqual(restored.progress.heroes["jeanne"].xp, 12)
            with self.assertRaises(RuleError):
                restored.route_transition("retreat")
            restored.abandon_encounter()  # Explicit abandon, no victory/reward.
            with self.assertRaises(RuleError):
                restored.route_transition("victory_return")
            back = restored.route_transition("retreat")
            self.assertEqual(back["scene"], "arrival")
            self.assertEqual(back["spawn"], [1, 1])
            self.assertEqual(restored.route_state()["position"], [1, 1])
            self.assertEqual(restored.progress.inventory["potion"], 3)
            self.assertTrue(restored.progress.story_flags["quest_found"])
            restored.save(path)
            again = GameSession.load(path, self.content, self.project)
            self.assertEqual(again.recording(), restored.recording())

    def test_gate_rejection_is_atomic_and_direct_battle_bypass_forbidden(self):
        session = self.session
        before = session.recording()
        with self.assertRaises(RuleError):
            session.route_transition("to_arena")  # Missing portal flag
        with self.assertRaises(RuleError):
            session.route_transition("retreat")  # Wrong source
        with self.assertRaises(RuleError):
            session.route_transition("missing")
        with self.assertRaises(RuleError):
            session.start_mission(MISSION)  # No bypass via old tactical API
        with self.assertRaises(RuleError):
            session.start_fronts({"x": MISSION}, "x")
        self.assertEqual(session.recording(), before)
        session.progress.story_flags["portal_open"] = True
        session.progress.unlocked.clear()
        before = session.recording()
        with self.assertRaises(RuleError):
            session.route_transition("to_arena")  # Mission not available
        self.assertEqual(session.recording(), before)

    def test_malformed_authoring_and_spawn_rejected(self):
        for corrupt in (
            lambda p: p.scene_routes["links"][0].update(spawn=[True, 1]),
            lambda p: p.scene_routes["links"][0].update(spawn=[999, 0]),
            lambda p: p.scene_routes["links"][1].update(spawn=[2, 1]),
            lambda p: p.scene_routes["links"][0].update(destination="absent"),
            lambda p: p.scene_routes["links"][0].update(when={"untrusted": "x"}),
            lambda p: p.scene_routes.update(version=2),
            lambda p: p.scene_routes["links"].append(
                deepcopy(p.scene_routes["links"][0])),
        ):
            project = deepcopy(self.project)
            corrupt(project)
            with self.subTest(value=project.scene_routes):
                with self.assertRaises(RuleError):
                    project.validate(self.content)

    def test_checkpoint_forgery_and_missing_history_rejected(self):
        session = self.session
        session.progress.story_flags["portal_open"] = True
        session.route_transition("to_arena")
        original = session.recording()
        mutations = [
            lambda p: p.pop("scene_route"),
            lambda p: p["scene_route"].update(current="arrival"),
            lambda p: p["scene_route"].update(history=[]),
            lambda p: p["scene_route"].update(history=["retreat"]),
            lambda p: p["scene_route"].update(version=2),
            lambda p: p["scene_route"].update(history=["missing"]),
        ]
        for mutate in mutations:
            payload = deepcopy(original)
            mutate(payload)
            payload["digest"] = digest({
                key: val for key, val in payload.items() if key != "digest"})
            with self.subTest(payload=payload.get("scene_route")):
                with self.assertRaises(RuleError):
                    GameSession.from_recording(
                        payload, self.content, self.project)

    def test_authentic_victory_route_preserves_once_only_rewards(self):
        session = self.session
        session.progress.story_flags["portal_open"] = True
        session.route_transition("to_arena")
        session.execute({"kind": "interact", "unit": "jeanne", "object": "lever"})
        for _ in range(700):
            if session.active_battle.result:
                break
            session.execute(choose_command(session.active_battle))
        self.assertEqual(session.active_battle.result, "victory")
        self.assertEqual(session.progress.completed, [MISSION])
        gold = session.progress.gold
        xp = session.progress.heroes["jeanne"].xp
        session._settle()  # Re-running the settlement must be idempotent.
        self.assertEqual(session.progress.gold, gold)
        self.assertEqual(session.progress.heroes["jeanne"].xp, xp)
        session.return_to_campaign()
        route = session.route_transition("victory_return")
        self.assertEqual(route["scene"], "arrival")
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "victory.json"
            session.save(path)
            restored = GameSession.load(path, self.content, self.project)
            self.assertEqual(restored.recording(), session.recording())
            self.assertEqual(restored.progress.gold, gold)
            self.assertEqual(restored.progress.heroes["jeanne"].xp, xp)
            self.assertEqual(restored.progress.completed, [MISSION])


if __name__ == "__main__":
    unittest.main()
