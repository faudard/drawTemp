"""R9.D gates: real dispatcher pages, persistent toggles, replay and R1 edits."""
from copy import deepcopy
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.events import EventStudio
from sporebound.engine import Battle
from sporebound.event_composer import condition, action
from sporebound.event_pages import active_page, page_snapshot
from sporebound.model import Content
from sporebound.rules import default_rules
from sporebound.tactical_rpg3 import authored_rules_for_document


class R9DPageContracts(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.studio = EventStudio(AuthoringSession.new(content, project))

    def battle(self):
        data = self.studio.documents()["content"]
        rules = authored_rules_for_document(data)
        content = Content.from_dict(data, rules=rules)
        return Battle(content, MISSION, seed=71, rules=rules)

    def test_priority_selection_and_implicit_base_compatibility(self):
        self.studio.create(MISSION, "r9d_priority",
                           condition("tick", tick=0),
                           [action("message", text="base")])
        self.studio.add_page(
            MISSION, "r9d_priority", page_id="low", priority=10,
            condition=condition("tick", tick=0),
            actions=[action("message", text="low")])
        self.studio.add_page(
            MISSION, "r9d_priority", page_id="high", priority=20,
            condition=condition("tick", tick=0),
            actions=[action("message", text="high")])
        battle = self.battle()
        self.assertIn("r9d_priority", battle.fired)
        records = [row for row in battle.events
                   if row["kind"] == "trigger" and row["id"] == "r9d_priority"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["page"], "high")
        self.assertEqual(page_snapshot(battle, "r9d_priority")["active_page"],
                         "high")
        replay = Battle.replay(battle.recording(), rules=battle.rules)
        self.assertEqual(replay.digest(), battle.digest())

    def test_activation_deactivation_persisted_in_authenticated_journal(self):
        self.studio.create(MISSION, "r9d_target", condition("tick", tick=0),
                           [action("message", text="base")])
        self.studio.add_page(
            MISSION, "r9d_target", page_id="open", priority=80,
            enabled=False, condition=condition("tick", tick=0),
            actions=[action("message", text="La porte est ouverte")])
        self.studio.create(
            MISSION, "r9d_controller", condition("tick", tick=0),
            [{"kind": "event_state", "event": "r9d_target",
              "page": "open", "enabled": True}])
        # Source fires first; the target reads the same immutable journal.
        while [row["id"] for row in self.studio.events(MISSION)].index(
                "r9d_controller") > [row["id"] for row in self.studio.events(MISSION)].index(
                    "r9d_target"):
            self.studio.move_event(MISSION, "r9d_controller", -1)
        battle = self.battle()
        self.assertTrue(page_snapshot(battle, "r9d_target")["enabled"]["open"])
        rows = [row for row in battle.events if row["kind"] == "trigger"
                and row["id"] == "r9d_target"]
        self.assertEqual(rows[0]["page"], "open")
        self.assertTrue(any(row["kind"] == "event_state"
                            and row["event"] == "r9d_target"
                            for row in battle.events))
        self.assertEqual(Battle.replay(battle.recording()).digest(),
                         battle.digest())

    def test_deactivation_of_page_is_journaled_and_replayable(self):
        self.studio.create(MISSION, "r9d_disable_target",
                           condition("tick", tick=0),
                           [action("message", text="Garde")])
        self.studio.add_page(
            MISSION, "r9d_disable_target", page_id="visible",
            priority=40, condition=condition("tick", tick=0),
            actions=[action("message", text="Page visible")])
        self.studio.create(
            MISSION, "r9d_off", condition("tick", tick=0),
            [{"kind": "event_state", "event": "r9d_disable_target",
              "page": "visible", "enabled": False}])
        while [row["id"] for row in self.studio.events(MISSION)].index(
                "r9d_off") > [row["id"] for row in self.studio.events(MISSION)].index(
                    "r9d_disable_target"):
            self.studio.move_event(MISSION, "r9d_off", -1)
        battle = self.battle()
        status = page_snapshot(battle, "r9d_disable_target")
        self.assertFalse(status["enabled"]["visible"])
        self.assertEqual(status["active_page"], "base")
        self.assertEqual([row["page"] for row in battle.events
                          if row["kind"] == "trigger" and
                          row["id"] == "r9d_disable_target"], ["base"])
        self.assertEqual(Battle.replay(battle.recording()).digest(),
                         battle.digest())

    def test_repeat_never_fires_twice_at_same_tick_and_replays(self):
        self.studio.create(MISSION, "r9d_repeat", condition("tick", tick=0),
                           [action("message", text="Horloge")])
        self.studio.configure_page(MISSION, "r9d_repeat", "base",
                                   repeat=True, cooldown_ticks=1)
        battle = self.battle()
        before = page_snapshot(battle, "r9d_repeat")["fire_count"]["base"]
        battle._triggers()  # same tick: read-only guard prevents a duplicate
        self.assertEqual(page_snapshot(battle, "r9d_repeat")["fire_count"]["base"],
                         before)
        for _ in range(8):
            if battle.result:
                break
            battle.execute({"kind": "end"})
        after = page_snapshot(battle, "r9d_repeat")["fire_count"]["base"]
        self.assertGreaterEqual(after, before)
        rows = [row["tick"] for row in battle.events
                if row["kind"] == "trigger" and row["id"] == "r9d_repeat"]
        self.assertEqual(len(rows), len(set(rows)))
        self.assertEqual(Battle.replay(battle.recording()).digest(),
                         battle.digest())

    def test_real_game_session_checkpoint_restores_event_page_state(self):
        from drawtemp.core import GameProject
        from sporebound.game_session import GameSession
        self.studio.create(MISSION, "r9d_session", condition("tick", tick=0),
                           [action("message", text="Garde")])
        self.studio.configure_page(MISSION, "r9d_session", "base",
                                   repeat=True, cooldown_ticks=2)
        data = self.studio.documents()
        rules = authored_rules_for_document(data["content"])
        content = Content.from_dict(data["content"], rules=rules)
        project = GameProject.from_dict(data["project"], content)
        session = GameSession.new(content, project, "main")
        session.start_mission(MISSION)
        before = session.recording()
        restored = GameSession.from_recording(before, content, project)
        self.assertEqual(restored.recording(), before)
        self.assertEqual(
            page_snapshot(restored.active_battle, "r9d_session"),
            page_snapshot(session.active_battle, "r9d_session"))

    def test_authoring_undo_redo_and_invalid_page_are_atomic(self):
        self.studio.create(MISSION, "r9d_author", condition("tick", tick=0),
                           [action("message", text="original")])
        base = self.studio.documents()
        self.studio.add_page(
            MISSION, "r9d_author", page_id="locked", priority=30,
            condition=condition("interact", object_id="lever"),
            actions=[action("message", text="Levier")])
        self.assertEqual(len(self.studio.event_pages(MISSION, "r9d_author")), 2)
        self.studio.configure_page(MISSION, "r9d_author", "locked",
                                   enabled=False, repeat=True, cooldown_ticks=3)
        self.assertFalse(self.studio.event_pages(MISSION, "r9d_author")[1]["enabled"])
        self.studio.undo()
        self.assertTrue(self.studio.event_pages(MISSION, "r9d_author")[1]["enabled"])
        self.studio.undo()
        self.assertEqual(self.studio.documents()["content"], base["content"])
        self.studio.redo()
        self.assertEqual(len(self.studio.event_pages(MISSION, "r9d_author")), 2)
        baseline = self.studio.documents()
        with self.assertRaises(AuthoringError):
            self.studio.add_page(
                MISSION, "r9d_author", page_id="bad", priority=110,
                condition=condition("tick", tick=0),
                actions=[action("message", text="bad")])
        self.assertEqual(self.studio.documents(), baseline)
        with self.assertRaises(AuthoringError):
            self.studio.add_page(
                MISSION, "r9d_author", page_id="broken", priority=25,
                condition=condition("interact", object_id="missing_lever"),
                actions=[action("message", text="bad")])
        self.assertEqual(self.studio.documents(), baseline)
        self.studio.delete_page(MISSION, "r9d_author", "locked")
        self.assertEqual(len(self.studio.event_pages(MISSION, "r9d_author")), 1)

    def test_legacy_document_has_identical_default_manifest(self):
        content, _ = reference_project()
        raw = content.to_dict()
        from sporebound.event_pages import has_pages
        self.assertFalse(has_pages(raw))
        self.assertEqual(Battle(content, MISSION).rules.manifest(),
                         default_rules().manifest())


if __name__ == "__main__":
    unittest.main()
