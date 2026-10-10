"""2.5.3.2 synergy unlock Studio: stable paths, runtime parity, undo and safety."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.bonds import (event_sequence_count, group_key, unlock_progress,
                              unlock_rule_met)
from sporebound.editor import Document
from sporebound.model import Content, RuleError
from sporebound.synergy_authoring import (change_tree, delete_unlock, event_spec,
    leaf, preview, rows, save_unlock)


class SynergyUnlockAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.source = Content.load(DEFAULT_CONTENT).to_dict()
        self.before = deepcopy(self.source)

    def test_create_multi_branch_unlock_with_runtime_preview_parity(self):
        mission = leaf("completed_mission", mission="garden")
        kills = leaf("stat", stat="shared_kills", threshold=2)
        expression = change_tree(mission, "wrap", operator="all")
        expression = change_tree(expression, "append", value=kills)
        combo = save_unlock(self.source, "crossfire", ["momo", "luma"],
                            expression, hints={"hidden":"Une formation secrète",
                                               "clue":"Combattre ensemble"})
        self.assertEqual(self.source, self.before)
        self.assertEqual(combo["tactic_unlocks"][-1]["id"], "crossfire")
        self.assertEqual(rows(expression)[0]["label"], "ET — toutes les conditions")
        self.assertEqual(rows(expression)[1]["path"], (("all", 0),))
        self.assertEqual(rows(expression)[2]["path"], (("all", 1),))
        index = len(combo["tactic_unlocks"])-1
        result = preview(combo, index, stats={"shared_kills":2},
                         completed=["garden"])
        self.assertEqual(result["progress"], 1.0)
        self.assertTrue(result["met"])
        reference = combo["tactic_unlocks"][index]
        self.assertEqual(result["met"], unlock_rule_met(
            {"shared_kills":2}, reference["unlock"],
            completed={"garden"}, members=reference["members"]))
        self.assertEqual(result["progress"], unlock_progress(
            {"shared_kills":2}, reference["unlock"],
            completed={"garden"}, members=reference["members"]))
        self.assertFalse(preview(combo, index, stats={"shared_kills":1},
                                 completed=["garden"])["met"])

    def test_sequence_multi_event_secret_matching_count_target_and_sources(self):
        specs = [event_spec("status", status="slow"),
                 event_spec("forced_move", mode="push"),
                 event_spec("damage")]
        sequence = leaf("sequence", sequence=specs, count=2,
                        same_target=True, max_ticks=12, require_sources=True)
        combo = save_unlock(self.source, "crossfire", ["momo", "luma"], sequence)
        index = len(combo["tactic_unlocks"])-1
        events = []
        for offset in (0, 20):
            events.extend([
                {"kind":"status","status":"slow","source":"momo",
                 "unit":"boss","tick":1+offset},
                {"kind":"forced_move","mode":"push","source":"luma",
                 "unit":"boss","tick":3+offset},
                {"kind":"damage","source":"momo","unit":"boss",
                 "tick":6+offset}
            ])
        self.assertEqual(event_sequence_count(events, sequence,
                                               ["momo","luma"]), 2)
        self.assertTrue(preview(combo, index, events=events)["met"])
        self.assertFalse(preview(combo, index, events=events[:3])["met"])
        wrong = deepcopy(events)
        wrong[1]["unit"]="other"
        self.assertFalse(preview(combo, index, events=wrong)["met"])
        self.assertEqual(self.source, self.before)

    def test_tree_reordering_removal_and_nonempty_group_guarantee(self):
        root = leaf("stat", stat="missions_together", threshold=1)
        wrapped = change_tree(root, "wrap", operator="any")
        second = leaf("mission", mission="garden")
        combo = change_tree(wrapped, "append", value=second)
        before = deepcopy(combo)
        path = (("any",1),)
        updated = change_tree(combo, "replace", path=path,
                              value=leaf("completed_mission", mission="escape"))
        self.assertEqual(updated["any"][1], {"completed_mission":"escape"})
        self.assertEqual(combo, before)
        removed = change_tree(updated, "delete", path=path)
        self.assertEqual(removed, wrapped)
        with self.assertRaises(RuleError):
            change_tree(removed, "delete", path=(("any",0),))
        with self.assertRaises(RuleError):
            change_tree(updated, "replace", path=(("any",9),), value=second)
        with self.assertRaises(ValueError):
            change_tree(updated, "delete")

    def test_save_edit_delete_is_document_undoable(self):
        doc = Document(Content.from_dict(self.source))
        created = save_unlock(doc.data, "crossfire", ["momo","luma"],
                              leaf("stat", stat="rescues", threshold=3))
        doc.replace(created)
        index = len(doc.data["tactic_unlocks"])-1
        edited = save_unlock(doc.data, "crossfire", ["momo","luma"],
                             leaf("completed_mission", mission="garden"),
                             index=index)
        doc.replace(edited)
        self.assertEqual(doc.data["tactic_unlocks"][index]["unlock"],
                         {"completed_mission":"garden"})
        doc.undo()
        self.assertEqual(doc.data["tactic_unlocks"][index]["unlock"],
                         {"stat":"rescues","gte":3})
        doc.redo()
        self.assertEqual(doc.data["tactic_unlocks"][index]["unlock"],
                         {"completed_mission":"garden"})
        doc.replace(delete_unlock(doc.data, index))
        self.assertEqual(doc.data["tactic_unlocks"], self.before["tactic_unlocks"])
        self.assertEqual(self.source, self.before)

    def test_reject_invalid_group_tactic_mission_and_untrusted_hints(self):
        cases = [
            lambda: save_unlock(self.source, "unknown", ["momo","luma"],
                                leaf("stat", stat="rescues", threshold=2)),
            lambda: save_unlock(self.source, "encirclement", ["momo","luma"],
                                leaf("stat", stat="rescues", threshold=2)),
            lambda: save_unlock(self.source, "pincer", ["ziggy","momo"],
                                leaf("stat", stat="rescues", threshold=2)),
            lambda: save_unlock(self.source, "pincer", ["momo","momo"],
                                leaf("stat", stat="rescues", threshold=2)),
            lambda: save_unlock(self.source, "crossfire", ["momo","missing"],
                                leaf("stat", stat="rescues", threshold=2)),
            lambda: save_unlock(self.source, "crossfire", ["momo","luma"],
                                leaf("mission", mission="unknown")),
            lambda: save_unlock(self.source, "crossfire", ["momo","luma"],
                                leaf("stat", stat="rescues", threshold=2),
                                hints={"invalid":"something"}),
            lambda: preview(self.source, 0, stats={"shared_kills":-1}),
        ]
        for operation in cases:
            with self.subTest(operation=operation), self.assertRaises(RuleError):
                operation()
            self.assertEqual(self.source, self.before)

    def test_invalid_sequence_guards_and_canonical_group_identity(self):
        self.assertEqual(group_key(["ziggy", "momo"]),
                         group_key(["momo", "ziggy"]))
        with self.assertRaises(RuleError):
            leaf("sequence", sequence=[], count=1)
        with self.assertRaises(RuleError):
            leaf("sequence", sequence=[{"kind":"damage"}], count=0)
        with self.assertRaises(RuleError):
            event_spec("damage", unsupported="anything")
        with self.assertRaises(RuleError):
            leaf("stat", stat="shared_kills", threshold=True)


if __name__=="__main__":
    unittest.main()
