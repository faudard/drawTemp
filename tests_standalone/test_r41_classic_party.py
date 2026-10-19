"""R41.A contract, canonical ownership, migration and failure tests (headless)."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk import negotiate_sdk, rpg_turn_order
from drawtemp.sdk.reference import reference_project
from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.classic_party import EXTENSION
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.model import Content, RuleError


def party_fixture():
    content = Content.load(DEFAULT_CONTENT)
    project = GameProject.default(content)
    # R25 classic_rpg exists already; R41 must not silently change CT missions.
    project.game_modes = {
        "version": 1, "default": {"preset": "classic_rpg"},
        "scenes": {mission: {"preset": "srpg"} for mission in content.missions},
    }
    project.extensions[EXTENSION] = {
        "schema_version": 1,
        "data": {"version": 1, "campaigns": {
            "main": {
                "recruitable": ["jeanne", "margot"],
                "initial": ["jeanne"],
                "active": ["jeanne"],
                "max_active": 2,
            },
        }},
    }
    project.validate(content)
    return content, project


class ClassicPartyFoundationTests(unittest.TestCase):
    def test_authoring_roundtrip_and_inherited_ct_are_unchanged(self):
        content, project = party_fixture()
        self.assertEqual(GameProject.from_dict(
            json.loads(json.dumps(project.to_dict())), content).to_dict(),
            project.to_dict())
        session = GameSession.new(content, project, "main", seed=17)
        self.assertEqual(session.scene_profile()["combat"], "RPG_TURN")
        self.assertTrue(all(
            session.scene_profile(mid)["combat"] == "TACTICAL_CT"
            for mid in content.missions))
        self.assertEqual(session.party_state()["members"], ["jeanne"])
        self.assertEqual(set(session.progress.heroes), {"jeanne"})
        self.assertEqual(session.party_state()["events"], [])

    def test_recruit_activate_save_replay_and_existing_inventory_owner(self):
        content, project = party_fixture()
        session = GameSession.new(content, project, "main", seed=42)
        session.progress.inventory["potion"] = 2
        session.progress.gold = 125
        session.progress.hero("jeanne").xp = 120
        session.party_recruit("margot")
        session.party_set_active(["margot", "jeanne"])
        expected = session.recording()
        self.assertEqual(expected["classic_party"]["members"],
                         ["jeanne", "margot"])
        self.assertEqual(expected["classic_party"]["active"],
                         ["margot", "jeanne"])
        self.assertEqual(session.progress.heroes["jeanne"].xp, 120)
        self.assertEqual(session.progress.gold, 125)
        self.assertEqual(session.progress.inventory["potion"], 2)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "r41.json"
            session.save(path)
            restored = GameSession.load(path, content, project)
            self.assertEqual(restored.recording(), expected)
            self.assertEqual(restored.party_state(), session.party_state())
            self.assertEqual(restored.progress.inventory["potion"], 2)
            self.assertEqual(restored.progress.heroes["jeanne"].xp, 120)
            with self.assertRaises(RuleError):
                restored.party_recruit("margot")
            self.assertEqual(restored.recording(), expected)

    def test_invalid_changes_are_atomic_and_party_requires_idle_campaign(self):
        content, project = party_fixture()
        session = GameSession.new(content, project, "main")
        initial = session.recording()
        for action in (
            lambda: session.party_recruit("jeanne"),
            lambda: session.party_recruit("unknown"),
            lambda: session.party_set_active(["margot"]),
            lambda: session.party_set_active([]),
            lambda: session.party_set_active(["jeanne", "jeanne"]),
            lambda: session.party_set_active(["jeanne"]),
        ):
            with self.subTest(action=action), self.assertRaises(RuleError):
                action()
            self.assertEqual(session.recording(), initial)
        session.start_mission(next(iter(content.missions)))
        before = session.recording()
        with self.assertRaises(RuleError):
            session.party_recruit("margot")
        self.assertEqual(session.recording(), before)

    def test_checkpoint_rejects_missing_extra_and_diverging_party_journal(self):
        content, project = party_fixture()
        session = GameSession.new(content, project, "main")
        session.party_recruit("margot")
        valid = session.recording()
        cases = []
        missing = deepcopy(valid)
        missing.pop("classic_party")
        cases.append(missing)
        extra = deepcopy(valid)
        extra["classic_party"]["unknown"] = True
        cases.append(extra)
        divergent = deepcopy(valid)
        divergent["classic_party"]["active"] = ["margot"]
        cases.append(divergent)
        duplicate = deepcopy(valid)
        duplicate["classic_party"]["events"].append(
            {"op": "recruit", "hero": "margot"})
        cases.append(duplicate)
        future = deepcopy(valid)
        future["classic_party"]["version"] = 2
        cases.append(future)
        for altered in cases:
            altered["digest"] = digest({
                k: v for k, v in altered.items() if k != "digest"})
            with self.subTest(keys=altered["classic_party"] if
                              "classic_party" in altered else "missing"):
                with self.assertRaises(RuleError):
                    GameSession.from_recording(altered, content, project)
        self.assertEqual(GameSession.from_recording(
            valid, content, project).recording(), valid)

    def test_invalid_schema_unknown_actor_profile_and_overcapacity(self):
        content, project = party_fixture()
        problems = [
            lambda p: p.extensions[EXTENSION]["data"].update(version=2),
            lambda p: p.extensions[EXTENSION]["data"].update(extra=True),
            lambda p: p.extensions[EXTENSION]["data"]["campaigns"]["main"].update(
                recruitable=["jeanne", "inexistent"]),
            lambda p: p.extensions[EXTENSION]["data"]["campaigns"]["main"].update(
                recruitable=["jeanne", "jeanne"]),
            lambda p: p.extensions[EXTENSION]["data"]["campaigns"]["main"].update(
                max_active=True),
            lambda p: p.extensions[EXTENSION]["data"]["campaigns"]["main"].update(
                active=["margot"]),
            lambda p: p.extensions[EXTENSION]["data"]["campaigns"].update(
                nonexistent=p.extensions[EXTENSION]["data"]["campaigns"]["main"]),
            lambda p: setattr(p, "game_modes", {}),
        ]
        for mutate in problems:
            altered = deepcopy(project)
            mutate(altered)
            with self.subTest(mutate=mutate), self.assertRaises(RuleError):
                altered.validate(content)

    def test_legacy_replay_and_schema_are_not_changed(self):
        content, legacy = reference_project()
        previous = GameSession.new(content, legacy, "main", seed=17).recording()
        self.assertNotIn("classic_party", previous)
        self.assertNotIn(EXTENSION, legacy.to_dict().get("extensions", {}))
        self.assertEqual(GameSession.from_recording(
            previous, content, legacy).recording(), previous)
        with self.assertRaises(RuleError):
            GameSession.new(content, legacy, "main").party_state()
        forged = deepcopy(previous)
        forged["classic_party"] = {"version": 1, "members": ["jeanne"],
                                   "active": ["jeanne"], "events": []}
        forged["digest"] = digest({k: v for k, v in forged.items()
                                   if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(forged, content, legacy)

    def test_turn_order_is_deterministic_bounded_and_not_ct(self):
        actors = [{"id": "jeanne", "speed": 12, "team": "party"},
                  {"id": "wolf", "speed": 15, "team": "enemy"},
                  {"id": "margot", "speed": 12, "team": "party"}]
        self.assertEqual(rpg_turn_order(actors), ("wolf", "jeanne", "margot"))
        self.assertEqual(rpg_turn_order(list(reversed(actors))),
                         ("wolf", "jeanne", "margot"))
        for malformed in (
            [], [{"id": "hero", "speed": True, "team": "party"}],
            actors + [deepcopy(actors[0])],
            [{"id": "x", "speed": 1, "team": "unknown"}],
            [{"id": "x", "speed": 0, "team": "party"}],
            [{"id": "x", "speed": 1, "team": "party", "attack": 42}],
        ):
            with self.subTest(malformed=malformed), self.assertRaises(RuleError):
                rpg_turn_order(malformed)
        self.assertTrue(negotiate_sdk(required_features=[
            "classic-party.v1", "rpg-turn-order.v1"]).compatible)


if __name__ == "__main__":
    unittest.main()
