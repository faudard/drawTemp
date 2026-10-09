"""Optional siege campaign gates, partial tactical objectives and replay."""
from copy import deepcopy
import unittest

from examples.siege_fronts import SIEGE_CAMPAIGN, siege_session
from examples.siege_scenarios import siege_content
from examples.siege_strategy_demo import demo as strategy_demo
from sporebound.fronts import MultiFrontSession
from sporebound.model import Content, RuleError


def custom_content():
    data = siege_content().to_dict()
    courtyard = next(m for m in data["missions"] if m["id"] == "castle_courtyard")
    stone = next(o for o in courtyard["objects"] if o["id"] == "stone_drop")
    stone["pos"] = [2, 3]
    throne = next(m for m in data["missions"] if m["id"] == "castle_throne")
    throne["units"] = [
        u for u in throne["units"]
        if u["id"] in {"captain", "engineer", "castellan"}]
    boss = next(u for u in throne["units"] if u["id"] == "castellan")
    boss.update(pos=[2, 3], hp=1, max_hp=1, speed=5)
    return Content.from_dict(data)


def fixture(content=None, *, seed=3, focused="supplies"):
    example = siege_session(seed=seed, contested=True, campaign=True)
    return MultiFrontSession(
        content or siege_content(), example.missions, focused,
        seed=seed, links=example.links, specs=example.initial_specs,
        logistics=example.initial_logistics, campaign=SIEGE_CAMPAIGN)


def negotiate_gate(s):
    s.switch("gate")
    s.execute({"kind": "start_battle"})
    s.negotiate_front("gate")


class SiegeCampaignTests(unittest.TestCase):
    def test_final_throne_starts_locked_and_no_unauthenticated_bypass(self):
        s = siege_session(contested=True, campaign=True)
        self.assertEqual(s.recording()["version"], 5)
        self.assertFalse(s.state()["campaign"]["unlocked"])
        before = s.digest()
        with self.assertRaises(RuleError):
            s.switch("throne")
        self.assertEqual(before, s.digest())
        self.assertEqual(s.state()["campaign"]["status"], "in_progress")
        with self.assertRaises(RuleError):
            fixture(focused="throne")

    def test_negotiation_pays_real_supplies_and_weakened_throne_garrison(self):
        s = fixture(custom_content())
        negotiate_gate(s)
        self.assertEqual(s.timeline.fronts["gate"]["status"], "negotiated")
        self.assertEqual(s.logistics.supplies["player"], 3)
        self.assertEqual(s.timeline.fronts["throne"]["strength"], 6)
        self.assertFalse(s.state()["campaign"]["unlocked"])
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(), s.digest())

    def test_partial_requires_real_sabotage_not_arbitrary_claim(self):
        s = fixture(custom_content())
        negotiate_gate(s)
        s.switch("courtyard")
        s.execute({"kind": "start_battle"})
        before = s.digest()
        with self.assertRaises(RuleError):
            s.partial_front("courtyard")
        self.assertEqual(s.digest(), before)
        s.execute({"kind": "interact", "object": "stone_drop"})
        # The active player has acted. Only commit a partial result at a
        # safe boundary, after finishing the tactical activation.
        with self.assertRaises(RuleError):
            s.partial_front("courtyard")
        s.execute({"kind": "end"})
        s.partial_front("courtyard")
        self.assertEqual(s.timeline.fronts["courtyard"]["status"], "partial")
        self.assertEqual(s.timeline.fronts["courtyard"]["strength"], 8)
        self.assertEqual(s.timeline.fronts["throne"]["strength"], 4)
        self.assertTrue(s.state()["campaign"]["unlocked"])
        self.assertEqual(s.state()["campaign"]["status"], "throne_unlocked")
        s.switch("throne")
        self.assertEqual(s.active.unit("captain").hp, 37)
        self.assertEqual(MultiFrontSession.replay(s.recording()).state(), s.state())

    def test_boss_kill_finishes_entire_campaign_not_only_front(self):
        s = fixture(custom_content())
        negotiate_gate(s)
        s.switch("courtyard")
        s.execute({"kind": "start_battle"})
        s.execute({"kind": "interact", "object": "stone_drop"})
        s.execute({"kind": "end"})
        s.partial_front("courtyard")
        s.switch("throne")
        s.execute({"kind": "start_battle"})
        self.assertEqual(s.active.active_id, "captain")
        s.execute({"kind": "act", "skill": "attack", "cell": [2, 3]})
        self.assertEqual(s.active.result, "victory")
        self.assertEqual(s.timeline.fronts["throne"]["status"], "victory")
        self.assertEqual(s.state()["campaign"]["status"], "victory")
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(), s.digest())

    def test_retreat_blocks_throne_and_costs_courtyard_strength_once(self):
        s = fixture()
        s.set_doctrine("gate", "retreat")
        s.advance()
        self.assertEqual(s.timeline.fronts["gate"]["status"], "withdrawn")
        self.assertEqual(s.timeline.fronts["courtyard"]["strength"], 5)
        self.assertEqual(s.state()["campaign"]["status"], "blocked")
        self.assertEqual(len([e for e in s.timeline.events
                              if e["kind"] == "campaign_retreat_cost"]), 1)
        s.advance()
        self.assertEqual(len([e for e in s.timeline.events
                              if e["kind"] == "campaign_retreat_cost"]), 1)
        with self.assertRaises(RuleError):
            s.switch("throne")
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(), s.digest())

    def test_explicit_withdrawal_is_logged_and_reduces_connected_front(self):
        s = fixture()
        s.switch("gate")
        s.execute({"kind": "start_battle"})
        s.withdraw_front("gate")
        self.assertEqual(s.timeline.fronts["gate"]["status"], "withdrawn")
        self.assertEqual(s.timeline.fronts["courtyard"]["strength"], 6)
        self.assertFalse(s.state()["campaign"]["unlocked"])
        self.assertEqual(s.state()["campaign"]["status"], "blocked")
        self.assertEqual(MultiFrontSession.replay(s.recording()).digest(), s.digest())

    def test_invalid_cost_and_bad_objective_rules_rejected(self):
        example = siege_session(contested=True, campaign=True)
        specs = []
        broken = deepcopy(SIEGE_CAMPAIGN)
        broken["required_fronts"]["gate"] = ["victory", "withdrawn"]
        specs.append(broken)
        broken = deepcopy(SIEGE_CAMPAIGN)
        broken["partial"]["courtyard"]["object"] = "unknown"
        specs.append(broken)
        broken = deepcopy(SIEGE_CAMPAIGN)
        broken["partial"]["courtyard"]["event"] = "interact"
        specs.append(broken)
        broken = deepcopy(SIEGE_CAMPAIGN)
        broken["negotiation"]["gate"]["supplies"] = True
        specs.append(broken)
        broken = deepcopy(SIEGE_CAMPAIGN)
        broken["retreat"]["gate"]["target"] = "does_not_exist"
        specs.append(broken)
        for spec in specs:
            with self.subTest(spec=spec), self.assertRaises(RuleError):
                MultiFrontSession(siege_content(), example.missions, "supplies",
                                  campaign=spec)
        s = fixture()
        s.switch("gate")
        s.execute({"kind": "start_battle"})
        s.logistics.supplies["player"] = 1
        before = s.digest()
        with self.assertRaises(RuleError):
            s.negotiate_front("gate")
        self.assertEqual(s.digest(), before)

    def test_complete_negotiated_and_partial_throne_demo(self):
        session = strategy_demo()
        self.assertEqual(session.state()["campaign"]["status"], "victory")
        self.assertEqual(session.timeline.fronts["gate"]["status"], "negotiated")
        self.assertEqual(session.timeline.fronts["courtyard"]["status"], "partial")
        self.assertEqual(MultiFrontSession.replay(session.recording()).digest(),
                         session.digest())

    def test_campaign_policy_tamper_is_detected_even_without_actions(self):
        session = fixture()
        original = session.recording()
        tampered = deepcopy(original)
        tampered["campaign"]["negotiation"]["gate"]["supplies"] = 1
        with self.assertRaises(RuleError):
            MultiFrontSession.replay(tampered)
        tampered = deepcopy(original)
        tampered["campaign"]["required_fronts"]["gate"] = ["victory"]
        with self.assertRaises(RuleError):
            MultiFrontSession.replay(tampered)

    def test_legacy_v4_session_and_mid_campaign_restore(self):
        old = siege_session(contested=True, decisions=True)
        self.assertEqual(old.recording()["version"], 4)
        self.assertNotIn("campaign", old.state())
        self.assertEqual(MultiFrontSession.replay(old.recording()).digest(),
                         old.digest())
        s = fixture(custom_content())
        negotiate_gate(s)
        restored = MultiFrontSession.replay(s.recording())
        self.assertEqual(restored.initial_campaign, s.initial_campaign)
        self.assertEqual(restored.state(), s.state())
        tampered = deepcopy(s.recording())
        tampered["operations"][-1]["front"] = "supplies"
        with self.assertRaises(RuleError):
            MultiFrontSession.replay(tampered)


if __name__ == "__main__":
    unittest.main()
