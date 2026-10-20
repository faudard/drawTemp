"""R38.1 global search: canonical snapshots, scoped references and Qt smoke."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r38_global_search import GlobalSearchIndex


def editor():
    return AuthoringSession.new(*reference_project())


def enriched_pair():
    pair = editor().snapshot().to_dict()
    mid = pair["content"]["missions"][0]["id"]
    actor = pair["content"]["missions"][0]["units"][0]["id"]
    pair["project"]["assets"] = {
        "version": 1,
        "entries": [
            {"id": "hero-sprite", "kind": "sprite", "path": "art/hero.png"},
            {"id": "hero-idle", "kind": "animation", "loop": True,
             "frames": [{"sprite": "hero-sprite", "duration_ms": 100}]},
        ],
        "bindings": {"sprite": {"hero": "hero-sprite"}},
    }
    pair["project"].setdefault("extensions", {})["org.drawtemp.logic"] = {
        "schema_version": 1,
        "data": {"graphs": [{
            "schema_version": 1, "id": "gate-logic", "mission_id": mid,
            "entry": "start",
            "nodes": [
                {"id": "start", "kind": "event",
                 "params": {"kind": "interact", "object_id": "lever"}},
                {"id": "act", "kind": "action",
                 "params": {"kind": "despawn", "unit": actor}},
            ],
            "edges": [{"from": "start", "out": "next",
                       "to": "act", "in": "flow"}],
        }]},
    }
    pair["project"]["extensions"]["org.drawtemp.livingworld"] = {
        "schema_version": 1, "data": {
            "version": 1, "start_minute": 480, "ticks_per_minute": 2,
            "clock_policy": "exploration_only", "npcs": [],
            "factions": [{"id": "guild", "initial": 0}],
            "daily_quests": [{
                "id": "delivery", "faction": "guild", "min_reputation": -10,
                "start_minute": 480, "end_minute": 1000,
                "completion_flag": "delivery_day", "reward_gold": 10,
                "reputation_delta": 3,
            }],
        },
    }
    return pair, mid, actor


class GlobalSearchHeadlessTests(unittest.TestCase):
    def test_resources_deterministic_accents_facets_and_no_mutation(self):
        data, mid, _ = enriched_pair()
        before = deepcopy(data)
        one, two = GlobalSearchIndex(data), GlobalSearchIndex(data)
        self.assertEqual(one.search(), two.search())
        self.assertEqual(one.usages, two.usages)
        self.assertEqual(data, before)
        self.assertTrue(one.search("hero-sprite", families=("assets",)))
        self.assertEqual(one.search("delivery", families=("quests",))[0].resource_id,
                         "delivery")
        self.assertTrue(one.search("gate-logic", families=("logic_graphs",),
                                   mission_id=mid))
        self.assertEqual(one.search("gate-logic", families=("assets",)), ())
        self.assertEqual(one.search("missing-never-exists"), ())
        self.assertTrue(one.search("lisiere", families=("scenes",)))
        self.assertEqual(len({entry.key for entry in one.entries}), len(one.entries))
        self.assertIsNone(one.by_key[("assets", "", "hero-sprite")].navigate)
        with self.assertRaises(ValueError):
            one.search(limit=0)
        with self.assertRaises(ValueError):
            one.references(("maps", "", mid), "unknown")

    def test_scope_and_known_typed_usages_only(self):
        data, mid, actor = enriched_pair()
        index = GlobalSearchIndex(data)
        gate = ("objects", mid, "gate")
        lever = ("objects", mid, "lever")
        self.assertTrue(any(e.source == lever and e.field == "link"
                            for e in index.references(gate)))
        self.assertTrue(any(e.source == ("assets", "", "hero-idle")
                            for e in index.references(("assets", "", "hero-sprite"))))
        self.assertTrue(any(e.field == "asset_binding"
                            for e in index.references(("assets", "", "hero-sprite"))))
        self.assertTrue(any(e.source == ("quests", "", "delivery") and
                            e.field == "faction" for e in
                            index.references(("factions", "", "guild"))))
        graph = ("logic_graphs", mid, "gate-logic")
        node = ("graph_nodes", mid, "gate-logic/start")
        self.assertTrue(any(e.source == graph for e in index.references(node)))
        self.assertTrue(any(e.source == node and e.field == "object_id"
                            for e in index.references(lever)))
        self.assertTrue(any(e.source == ("graph_nodes", mid, "gate-logic/act")
                            for e in index.references(("actors", mid, actor))))
        self.assertFalse(index.references(("assets", "", "hero-idle"), "incoming"))
        with self.assertRaises(KeyError):
            index.references(("objects", mid, "not-found"))

        # Same ID in a different mission is NOT a usage of the first object.
        duplicate = deepcopy(data["content"]["missions"][0])
        duplicate["id"] = "other"
        data["content"]["missions"].append(duplicate)
        index = GlobalSearchIndex(data)
        self.assertEqual({e.source[1] for e in index.references(gate)
                          if e.field == "link"}, {mid})
        self.assertTrue(any(e.source[1] == "other" for e in
                            index.references(("objects", "other", "gate"))))

    def test_revision_rebuild_after_undo(self):
        owner = editor()
        before = GlobalSearchIndex(owner.snapshot())
        self.assertEqual(before.revision, 0)
        def rename(project):
            project["title"] = "Recherche globale mise à jour"
            return project
        owner.apply(owner.preview_project(rename))
        after = GlobalSearchIndex(owner.snapshot())
        self.assertEqual(after.revision, 1)
        self.assertTrue(after.search("recherche globale", families=("project",)))
        self.assertFalse(before.search("recherche globale", families=("project",)))
        owner.undo()
        self.assertEqual(GlobalSearchIndex(owner.snapshot()).search(
            "recherche globale", families=("project",)), ())

    def test_headless_does_not_import_qt_or_tk(self):
        program = """
import sys
class NoUi:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('PySide6', 'tkinter'):
            raise AssertionError('Unexpected UI import')
sys.meta_path.insert(0, NoUi())
from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.r38_global_search import GlobalSearchIndex
session = AuthoringSession.new(*reference_project())
assert GlobalSearchIndex(session.snapshot()).search('gate')
"""
        subprocess.run([sys.executable, "-c", program], check=True,
                       capture_output=True, text=True)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 unavailable")
class GlobalSearchQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_studio_action_results_usages_and_navigation(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        from drawtemp.studio.r38_search_qt import GlobalSearchDialog
        with tempfile.TemporaryDirectory() as folder:
            win = StudioWindow(editor(), settings=QSettings(
                str(Path(folder) / "studio.ini"), QSettings.IniFormat))
            self.assertIn("global_search", win.commands)
            dialog = GlobalSearchDialog(win)
            dialog.query.setText("gate")
            candidates = [(index, hit) for index, hit in enumerate(dialog._hits)
                          if hit.family == "objects" and hit.resource_id == "gate"]
            self.assertEqual(len(candidates), 1)
            dialog.results.setCurrentRow(candidates[0][0])
            self.assertIn("lever", dialog.details.toPlainText())
            dialog.open_selection()
            self.assertEqual(len(win._selected), 1)
            self.assertEqual(win._selected[0].resource_id, "gate")
            win.close()


if __name__ == "__main__":
    unittest.main()
