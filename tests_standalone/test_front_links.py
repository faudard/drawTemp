"""Cross-front causal siege objectives, authoring errors and verified replay."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from examples.siege_fronts import SIEGE_LINKS, siege_session
from examples.siege_scenarios import siege_content
from sporebound.fronts import MultiFrontSession
from sporebound.model import Content, RuleError


class FrontLinkTests(TestCase):
    def fixture(self, focused="walls", *, content=None):
        return MultiFrontSession(
            content or siege_content(),
            {"walls": "castle_ramparts", "gate": "castle_ram",
             "courtyard": "castle_courtyard", "supplies": "castle_supply",
             "throne": "castle_throne"},
            focused, seed=3, links=SIEGE_LINKS)

    def content_with_nearby(self, object_id):
        raw = siege_content().to_dict()
        walls = next(m for m in raw["missions"] if m["id"] == "castle_ramparts")
        obj = next(o for o in walls["objects"] if o["id"] == object_id)
        obj["pos"] = [2, 3]
        return Content.from_dict(raw)

    def test_supply_raid_cancels_queued_and_future_reserves(self):
        session = siege_session(focused="supplies")
        session.reinforce("throne", [
            {"id": "marching_reserve", "name": "Reserve",
             "team": "enemy", "pos": [11, 7]}])
        session.execute({"kind": "start_battle"})
        session.execute({"kind": "interact", "object": "supply_cache"})
        self.assertEqual(session.applied_links, {"cut_supply_route"})
        self.assertIn("throne", session.blocked_reinforcements)
        self.assertNotIn("throne", session.pending_reinforcements)
        before = session.digest()
        with self.assertRaises(RuleError):
            session.reinforce("throne", [
                {"id": "later", "name": "Later", "team": "enemy",
                 "pos": [11, 7]}])
        self.assertEqual(session.digest(), before)
        session.execute({"kind": "end"})
        session.switch("throne")
        self.assertEqual(session.active.encounter.pending, [])
        self.assertTrue(all(action["kind"] not in {"wave", "queue_wave"}
                            for t in session.active.mission.triggers
                            for action in t["actions"]))
        replay = MultiFrontSession.replay(session.recording())
        self.assertEqual(replay.digest(), session.digest())
        self.assertEqual(replay.state(), session.state())

    def test_blocked_boss_phase_keeps_non_reinforcement_actions(self):
        raw = siege_content().to_dict()
        throne = next(m for m in raw["missions"] if m["id"] == "castle_throne")
        next(u for u in throne["units"] if u["id"] == "castellan")["hp"] = 32
        session = self.fixture("supplies", content=Content.from_dict(raw))
        session.execute({"kind": "start_battle"})
        session.execute({"kind": "interact", "object": "supply_cache"})
        session.execute({"kind": "end"})
        session.switch("throne")
        session.execute({"kind": "start_battle"})
        self.assertIn("haste", session.active.unit("castellan").statuses)
        self.assertFalse(any(u.id.startswith("throne_reserve_")
                             for u in session.active.units))
        self.assertEqual(session.active.encounter.pending, [])
        self.assertIn("castellan_second_phase", session.active.fired)
        self.assertEqual(MultiFrontSession.replay(session.recording()).digest(),
                         session.digest())

    def test_raising_herse_opens_unloaded_gate_and_weakens_courtyard(self):
        session = self.fixture(content=self.content_with_nearby("portcullis_lever"))
        session.execute({"kind": "start_battle"})
        session.execute({"kind": "interact", "object": "portcullis_lever"})
        self.assertIn("raise_herse", session.applied_links)
        self.assertEqual(session.timeline.fronts["courtyard"]["opposition"], 7)
        self.assertTrue(session.front_overrides["gate"]["main_gate"]["open"])
        session.execute({"kind": "end"})
        session.switch("gate")
        gate = next(o for o in session.active.mission.objects
                    if o["id"] == "main_gate")
        self.assertTrue(gate["open"])
        self.assertFalse(session.active.board.tile((8, 3)).blocked)
        session.switch("courtyard")
        self.assertEqual(session.active.unit("defender").hp, 37)
        self.assertEqual(MultiFrontSession.replay(session.recording()).digest(),
                         session.digest())

    def test_sabotage_updates_already_loaded_courtyard_defense(self):
        session = self.fixture(content=self.content_with_nearby("boiling_oil"))
        session.switch("courtyard")
        session.switch("walls")
        session.execute({"kind": "start_battle"})
        session.execute({"kind": "interact", "object": "boiling_oil"})
        defense = next(o for o in session.battles["courtyard"].mission.objects
                       if o["id"] == "stone_drop")
        self.assertTrue(defense["disabled"])
        self.assertEqual(session.applied_links, {"secure_ramparts"})
        self.assertEqual(MultiFrontSession.replay(session.recording()).digest(),
                         session.digest())

    def test_validation_rejects_invalid_links(self):
        originals = deepcopy(SIEGE_LINKS)
        variants = [
            lambda r: r[0].update(source="missing"),
            lambda r: r[0].update(event="guess"),
            lambda r: r[0].update(match={"object": "missing"}),
            lambda r: r[0]["effects"][0].update(object="missing"),
            lambda r: r[0]["effects"][0].update(front="walls"),
            lambda r: r[0]["effects"][1].update(amount=-1),
            lambda r: r[0]["effects"][1].update(amount=True),
            lambda r: r.append(deepcopy(r[0])),
            lambda r: r[0]["effects"][1].update(extra="x"),
        ]
        for mutate in variants:
            links = deepcopy(originals)
            mutate(links)
            with self.subTest(links=links), self.assertRaises(RuleError):
                MultiFrontSession(siege_content(),
                    {"walls": "castle_ramparts", "gate": "castle_ram",
                     "courtyard": "castle_courtyard", "supplies": "castle_supply",
                     "throne": "castle_throne"},
                    "supplies", links=links)

    def test_invalid_link_effect_rolls_back_all_fronts(self):
        from sporebound import front_links
        session = self.fixture("supplies")
        session.execute({"kind": "start_battle"})
        before = session.digest()
        original_apply = front_links.apply

        def broken_apply(active, link):
            original_apply(active, link)
            raise RuntimeError("injected effect failure")

        with patch("sporebound.front_links.apply", side_effect=broken_apply):
            with self.assertRaises(RuntimeError):
                session.execute({"kind": "interact", "object": "supply_cache"})
        self.assertEqual(session.digest(), before)
        self.assertEqual(len(session.history), 1)
        session.execute({"kind": "interact", "object": "supply_cache"})
        self.assertEqual(session.applied_links, {"cut_supply_route"})

    def test_link_tampering_detected_and_v1_recording_preserved(self):
        session = self.fixture("supplies")
        session.execute({"kind": "start_battle"})
        session.execute({"kind": "interact", "object": "supply_cache"})
        recording = session.recording()
        tampered = deepcopy(recording)
        tampered["links"][2]["effects"][0]["front"] = "gate"
        with self.assertRaises(RuleError):
            MultiFrontSession.replay(tampered)
        no_links = MultiFrontSession(siege_content(),
            {"supplies": "castle_supply", "throne": "castle_throne"}, "supplies")
        no_links.execute({"kind": "start_battle"})
        legacy = no_links.recording()
        legacy["version"] = 1
        legacy.pop("links")
        self.assertEqual(MultiFrontSession.replay(legacy).digest(), no_links.digest())


if __name__ == "__main__":
    import unittest
    unittest.main()
