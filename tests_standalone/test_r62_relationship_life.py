"""R62.B.2: deterministic, opt-in social lifecycle and canonical SDK save."""
from copy import deepcopy
import unittest

from drawtemp.sdk.simulation import Simulation, SimulationError
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from sporebound.relationship_life import (
    EXTENSION, RelationshipLife, validate_relationships,
)
from tests_standalone.test_r35_commerce import merchant_fixture


def social_spec():
    return {"version": 1, "relationships": [
        {"npc": "merchant", "initial": 5, "talk_gain": 3,
         "talk_activity": "trade",
         "gifts": [{"item": "epee_de_jacques", "gain": 7},
                   {"item": "cape_de_route", "gain": -4}]},
        {"npc": "traveler", "initial": -2, "talk_gain": 1,
         "talk_activity": "any", "gifts": []},
    ]}


def fixture():
    content, project = merchant_fixture()
    project.extensions[EXTENSION] = {
        "schema_version": 1, "data": social_spec(), "references": []}
    project.validate(content)
    return content, project


def start_market(session):
    session.progress.story_flags["market_open"] = True
    session.living_world_advance(2)


def next_day(session):
    clock = session._living_world
    session.living_world_advance(
        (1440 - clock.minute) * clock.spec["ticks_per_minute"])


class R62RelationshipTests(unittest.TestCase):
    def test_schema_rejects_unknown_npc_items_activity_and_bool(self):
        content, project = fixture()
        spec = social_spec()
        npcs = {"merchant", "traveler"}
        items = set(content.equipment)
        activities = {row["id"]: {stop["activity"] for stop in row["schedule"]}
                      for row in project.extensions["org.drawtemp.livingworld"]
                      ["data"]["npcs"]}
        self.assertEqual(validate_relationships(
            spec, npcs, items, npc_activities=activities), spec)
        edits = [
            lambda x: x["relationships"][0].update(npc="unknown"),
            lambda x: x["relationships"][0].update(talk_gain=True),
            lambda x: x["relationships"][0].update(talk_activity="missing"),
            lambda x: x["relationships"][0]["gifts"][0].update(item="missing"),
            lambda x: x["relationships"].append(deepcopy(x["relationships"][0])),
            lambda x: x["relationships"][0]["gifts"].append(
                deepcopy(x["relationships"][0]["gifts"][0])),
            lambda x: x.update(version=2),
        ]
        for edit in edits:
            altered = deepcopy(spec)
            edit(altered)
            with self.subTest(altered=altered), self.assertRaises(RuleError):
                validate_relationships(
                    altered, npcs, items, npc_activities=activities)
        without_r35 = deepcopy(project)
        del without_r35.extensions["org.drawtemp.livingworld"]
        with self.assertRaises(RuleError):
            without_r35.validate(content)

    def test_talk_schedule_and_daily_limit_are_deterministic(self):
        content, project = fixture()
        session = GameSession.new(content, project, "main", seed=62)
        before = session.recording()
        with self.assertRaises(RuleError):
            session.relationship_talk("merchant", "early")
        self.assertEqual(before, session.recording())
        start_market(session)
        self.assertTrue(session.relationship_talk("merchant", "talk-1"))
        self.assertEqual(session.relationship_state("merchant")
                         ["relationships"]["merchant"]["score"], 8)
        self.assertFalse(session.relationship_talk("merchant", "talk-1"))
        with self.assertRaises(RuleError):
            session.relationship_talk("merchant", "second-today")
        checkpoint = session.recording()
        with self.assertRaises(RuleError):
            session.relationship_talk("traveler", "talk-1")
        self.assertEqual(checkpoint, session.recording())
        next_day(session)
        self.assertEqual(session.relationship_state()["day"], 1)
        self.assertFalse(session.relationship_talk("merchant", "talk-1"))
        session.living_world_advance(480 * 2)
        self.assertTrue(session.relationship_talk("merchant", "talk-2"))
        self.assertEqual(session.relationship_state("merchant")
                         ["relationships"]["merchant"]["score"], 11)

    def test_gifts_atomic_inventory_replay_and_anti_duplication(self):
        content, project = fixture()
        session = GameSession.new(content, project, "main", seed=62)
        start_market(session)
        initial = session.recording()
        with self.assertRaises(RuleError):
            session.relationship_gift("merchant", "epee_de_jacques", "gift-1")
        self.assertEqual(session.recording(), initial)
        session.progress.inventory["epee_de_jacques"] = 2
        self.assertTrue(session.relationship_gift(
            "merchant", "epee_de_jacques", "gift-1"))
        self.assertEqual(session.progress.inventory["epee_de_jacques"], 1)
        self.assertEqual(session.relationship_state("merchant")
                         ["relationships"]["merchant"]["score"], 12)
        self.assertFalse(session.relationship_gift(
            "merchant", "epee_de_jacques", "gift-1"))
        with self.assertRaises(RuleError):
            session.relationship_gift("merchant", "cape_de_route", "gift-1")
        with self.assertRaises(RuleError):
            session.relationship_gift("merchant", "epee_de_jacques", "gift-2")
        saved = session.recording()
        restored = GameSession.from_recording(saved, content, project)
        self.assertEqual(restored.recording(), saved)
        self.assertFalse(restored.relationship_gift(
            "merchant", "epee_de_jacques", "gift-1"))
        self.assertEqual(restored.progress.inventory["epee_de_jacques"], 1)
        for mutate in [
            lambda x: x["relationships"]["scores"].update(merchant=100),
            lambda x: x["relationships"]["journal"][0].update(day=4),
            lambda x: x["relationships"]["journal"].append(
                deepcopy(x["relationships"]["journal"][0])),
            lambda x: x["relationships"].update(day=5),
        ]:
            forged = deepcopy(saved)
            mutate(forged)
            forged["digest"] = digest(
                {k: v for k, v in forged.items() if k != "digest"})
            with self.subTest(forged=forged["relationships"]), self.assertRaises(RuleError):
                GameSession.from_recording(forged, content, project)

    def test_core_replay_is_seed_independent_and_saturated(self):
        content, _project = fixture()
        data = social_spec()
        data["relationships"][0]["initial"] = 99
        world_npcs = {"merchant", "traveler"}
        social = RelationshipLife(data, world_npcs, set(content.equipment))
        social.command("talk", "merchant", "one")
        self.assertEqual(social.view("merchant")["relationships"]
                         ["merchant"]["score"], 100)
        social.sync(1)
        social.command("talk", "merchant", "two")
        self.assertEqual(social.view("merchant")["relationships"]
                         ["merchant"]["score"], 100)
        snapshot = social.snapshot()
        restored = RelationshipLife(data, world_npcs, set(content.equipment))
        restored.restore(snapshot)
        self.assertEqual(restored.snapshot(), snapshot)

    def test_sdk_revisions_and_disabled_project_preserve_old_slots(self):
        content, project = fixture()
        session = GameSession.new(content, project, "main")
        sdk = Simulation(session)
        view = sdk.relationship_state()
        with self.assertRaises(TypeError):
            view["relationships"]["merchant"]["score"] = 100
        # Merchant at 479 is sleeping, but traveler accepts any activity.
        transition = sdk.relationship_talk("traveler", "sdk-talk",
                                            expected_revision=0)
        self.assertEqual(transition.snapshot.revision, 1)
        with self.assertRaises(SimulationError) as error:
            sdk.relationship_talk("traveler", "stale", expected_revision=0)
        self.assertEqual(error.exception.code, "stale_revision")
        content, project = merchant_fixture()
        legacy = GameSession.new(content, project, "main")
        self.assertNotIn("relationships", legacy.recording())
        self.assertEqual(GameSession.from_recording(
            legacy.recording(), content, project).recording(),
            legacy.recording())


if __name__ == "__main__":
    unittest.main()
