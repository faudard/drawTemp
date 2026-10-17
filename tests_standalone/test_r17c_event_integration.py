"""R17.C1 — R9.D integration survives ordinary R9 graph edits and replay.

The historical branch that carried R9.D was merged into an intermediate branch,
not master. These checks protect the recovered canonical integration.
"""
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.events import EventStudio
from sporebound.event_composer import action, condition
from sporebound.engine import Battle
from sporebound.model import Content
from sporebound.tactical_rpg3 import authored_rules_for_document


class R17CRecoveredPages(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.studio = EventStudio(AuthoringSession.new(content, project))

    def test_priority_and_undo_survive_reordering_and_action_edit(self):
        self.studio.create(MISSION, "r17_pages", condition("tick", tick=0),
                           [action("message", text="base")])
        self.studio.add_page(
            MISSION, "r17_pages", page_id="lever_open", priority=60,
            condition=condition("tick", tick=0),
            actions=[action("message", text="open")])
        self.studio.create(MISSION, "r17_companion", condition("tick", tick=0),
                           [action("message", text="other")])
        self.studio.move_event(MISSION, "r17_pages", 1)
        self.studio.add_action(
            MISSION, "r17_pages", action("message", text="after_edit"))
        pages = self.studio.event_pages(MISSION, "r17_pages")
        self.assertEqual(pages[1]["priority"], 60)
        self.assertEqual(pages[1]["actions"][0]["text"], "open")
        self.studio.undo()
        self.assertEqual(len(self.studio.event(MISSION, "r17_pages")["actions"]), 1)
        self.studio.redo()
        self.assertEqual(len(self.studio.event(MISSION, "r17_pages")["actions"]), 2)
        document = self.studio.documents()["content"]
        rules = authored_rules_for_document(document)
        battle = Battle(Content.from_dict(document, rules=rules), MISSION,
                        seed=19, rules=rules)
        trigger_events = [e for e in battle.events
                          if e["kind"] == "trigger" and e["id"] == "r17_pages"]
        self.assertEqual(trigger_events[0]["page"], "lever_open")
        self.assertEqual(Battle.replay(battle.recording()).digest(), battle.digest())

    def test_event_pages_remain_typed_and_validation_is_atomic(self):
        self.studio.create(MISSION, "r17_checks", condition("tick", tick=0),
                           [action("message", text="base")])
        self.studio.add_page(
            MISSION, "r17_checks", page_id="valid", priority=10,
            condition=condition("tick", tick=0),
            actions=[action("message", text="valid")])
        before = self.studio.documents()
        with self.assertRaises(Exception):
            self.studio.configure_page(MISSION, "r17_checks", "valid",
                                       repeat=True, cooldown_ticks=-5)
        self.assertEqual(self.studio.documents(), before)
        self.assertEqual(self.studio.event_pages(MISSION, "r17_checks")[1]["id"],
                         "valid")


if __name__ == "__main__":
    unittest.main()
