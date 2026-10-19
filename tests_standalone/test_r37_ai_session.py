"""R37.B — GameSession-owned opt-in AI state and replay-bound decisions."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.reference import MISSION, reference_project
from sporebound.advanced_ai import EXTENSION
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.model import RuleError
from tests_standalone.test_r35_living_world import fixture as living_fixture


def policy(identifier, action, *, when=None, terms=None, base=0):
    return {"id": identifier, "action": action, "base": base,
            "when": when or {}, "terms": terms or {}}


def enable(project, actor_id, mode, policies):
    project.extensions[EXTENSION] = {
        "schema_version": 1,
        "data": {"version": 1, "agents": [{
            "id": actor_id, "mode": mode, "policies": policies,
        }]},
        "references": [],
    }


def realtime_fixture():
    content, project = living_fixture()
    enable(project, "merchant", "realtime", [
        policy("close", "rest", when={"activity": "sleep"}, base=1),
        policy("open", "trade", when={"activity": "trade",
                                    "blackboard.alert": True}, base=3),
        policy("fallback", "patrol", when={"same_scene": False}, base=0),
    ])
    project.validate(content)
    return content, project


class AdvancedAISessionTests(unittest.TestCase):
    def test_realtime_npc_context_and_diagnostic_memory_roundtrip(self):
        content, project = realtime_fixture()
        source = project.to_dict()
        self.assertEqual(GameProject.from_dict(source, content).to_dict(), source)
        session = GameSession.new(content, project, "main", seed=42)
        self.assertIn("advanced_ai", session.recording())
        before = session.recording()
        state = session.ai_state("merchant")
        self.assertEqual(state["values"], {})
        report = session.ai_decision_preview("merchant")
        self.assertEqual(report["action"], "rest")
        self.assertEqual(report["tick"], 0)
        self.assertEqual(report["mode"], "realtime")
        self.assertEqual(session.recording(), before)  # preview is pure
        self.assertTrue(report["used_fallback"] is False)
        self.assertEqual(session.ai_decision_context("merchant")["facts"],
                         {"activity": "sleep", "same_scene": True})
        self.assertEqual(session.ai_remember("merchant", {"alert": True}),
                         {"schema_version": 1, "actor_id": "merchant",
                          "updated_tick": 0, "values": {"alert": True}})
        self.assertEqual(state["values"], {})  # detached state
        session.progress.story_flags["market_open"] = True
        session.living_world_advance(2)
        decision = session.ai_decision_preview("merchant")
        self.assertEqual(decision["action"], "trade")
        self.assertEqual(decision["tick"], 2)
        self.assertEqual(decision["policy_id"], "open")
        checkpoint = session.recording()
        self.assertEqual(len(checkpoint["advanced_ai"]["history"]), 1)
        with TemporaryDirectory() as temporary:
            save = Path(temporary) / "advanced.json"
            session.save(save)
            restored = GameSession.load(save, content, project)
        self.assertEqual(restored.recording(), checkpoint)
        self.assertEqual(restored.ai_decision_preview("merchant"), decision)
        restored.ai_remember("merchant", {"alert": False})
        self.assertEqual(restored.ai_decision_preview("merchant")["action"],
                         "wait")  # no eligible policy at the market
        self.assertEqual(session.ai_state("merchant")["values"]["alert"], True)
        self.assertNotEqual(restored.recording(), checkpoint)

    def test_realtime_advance_and_cross_mode_pause(self):
        content, project = realtime_fixture()
        session = GameSession.new(content, project, "main")
        session.ai_remember("merchant", {"alert": True})
        session.route_realtime_step(1, 0)
        session.ai_remember("merchant", {"alert": False})
        self.assertEqual(session.ai_state("merchant")["updated_tick"], 1)
        session.progress.story_flags["portal_open"] = True
        session.route_transition("to_arena")
        with self.assertRaises(RuleError):
            session.ai_remember("merchant", {"alert": True})
        self.assertEqual(session.ai_state("merchant")["values"]["alert"], False)
        self.assertEqual(GameSession.from_recording(
            session.recording(), content, project).recording(),
            session.recording())

    def test_tactical_preview_is_opt_in_and_does_not_change_ct(self):
        content, project = reference_project()
        probe = GameSession.new(content, project, "main", seed=17)
        battle = probe.start_mission(MISSION)
        actor_id = next(unit.id for unit in battle.units if unit.alive)
        enable(project, actor_id, "ct", [
            policy("test", "guard", terms={"hp": 1}, base=1),
        ])
        session = GameSession.new(content, project, "main", seed=17)
        session.start_mission(MISSION)
        before = session.recording()
        report = session.ai_decision_preview(actor_id)
        self.assertEqual(report["mode"], "ct")
        self.assertEqual(report["action"], "guard")
        self.assertEqual(report["tick"], session.battle.tick)
        self.assertEqual(session.recording(), before)
        with self.assertRaises(RuleError):
            session.ai_remember(actor_id, {"alert": True})
        self.assertEqual(session.recording(), before)
        restored = GameSession.from_recording(before, content, project)
        self.assertEqual(restored.ai_decision_preview(actor_id), report)

    def test_refuse_journal_forgery_even_after_outer_checksum_is_rebuilt(self):
        content, project = realtime_fixture()
        session = GameSession.new(content, project, "main")
        session.living_world_advance(2)
        session.ai_remember("merchant", {"alert": True})
        checkpoint = session.recording()
        corruptions = [
            lambda d: d["advanced_ai"]["blackboards"]["merchant"]["values"].update(alert=False),
            lambda d: d["advanced_ai"]["history"][0].update(tick=3),
            lambda d: d["advanced_ai"]["history"][0].update(actor_id="forged"),
            lambda d: d["advanced_ai"].update(version=True),
            lambda d: d["advanced_ai"]["blackboards"]["merchant"].update(
                schema_version=3),
        ]
        for mutate in corruptions:
            row = deepcopy(checkpoint)
            mutate(row)
            row["digest"] = digest({k: v for k, v in row.items()
                                    if k != "digest"})
            with self.subTest(mutate=mutate), self.assertRaises(RuleError):
                GameSession.from_recording(row, content, project)

    def test_missing_unexpected_and_future_memory_rejected(self):
        content, project = realtime_fixture()
        session = GameSession.new(content, project, "main")
        snapshot = session.recording()
        missing = deepcopy(snapshot)
        missing.pop("advanced_ai")
        missing["digest"] = digest({k: v for k, v in missing.items()
                                    if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(missing, content, project)
        future = deepcopy(snapshot)
        future["advanced_ai"]["history"].append({
            "actor_id": "merchant", "tick": 4, "changes": {"alert": True}})
        future["advanced_ai"]["blackboards"]["merchant"].update(
            updated_tick=4, values={"alert": True})
        future["digest"] = digest({k: v for k, v in future.items()
                                   if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(future, content, project)
        legacy_content, legacy_project = living_fixture()
        legacy = GameSession.new(legacy_content, legacy_project, "main")
        self.assertNotIn("advanced_ai", legacy.recording())
        with self.assertRaises(RuleError):
            legacy.ai_state()
        forged = legacy.recording()
        forged["advanced_ai"] = snapshot["advanced_ai"]
        forged["digest"] = digest({k: v for k, v in forged.items()
                                   if k != "digest"})
        with self.assertRaises(RuleError):
            GameSession.from_recording(forged, legacy_content, legacy_project)

    def test_authored_agent_and_policy_validation_is_strict(self):
        content, project = realtime_fixture()
        changes = [
            lambda a: a.update(mode="unbounded"),
            lambda a: a.update(id="other"),
            lambda a: a["policies"][0].update({"script": "eval()"}),
            lambda a: a["policies"][0].update(base=True),
            lambda a: a["policies"].append(deepcopy(a["policies"][0])),
        ]
        for mutate in changes:
            p = deepcopy(project)
            agent = p.extensions[EXTENSION]["data"]["agents"][0]
            mutate(agent)
            with self.subTest(mutate=mutate), self.assertRaises(RuleError):
                p.validate(content)
        p = deepcopy(project)
        p.extensions[EXTENSION]["data"]["version"] = 2
        with self.assertRaises(RuleError):
            p.validate(content)


if __name__ == "__main__":
    unittest.main()
