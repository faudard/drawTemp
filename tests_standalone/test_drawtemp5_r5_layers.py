"""R5.6 map layer workspace: locks, isolated views and persistent sidecars."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError
from drawtemp.studio.map_authoring import MapStudio
from drawtemp.studio.map_layers import LayerWorkspace, LAYERS
from sporebound.map_layer_workspace import load_views, view_sidecar_path
from sporebound.model import RuleError


class LayerWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.studio = MapStudio.reference()
        self.studio.create("r5_layers", "Calques R5", 12, 12)
        self.mid = self.studio.mission_id

    def test_visibility_does_not_modify_content_history_or_gameplay(self):
        before = self.studio.snapshot()
        self.studio.layers.set_visible(self.mid, "Terrain", False)
        self.studio.layers.set_visible(self.mid, "Unités", False)
        self.studio.layers.set_opacity(self.mid, "Décors", 35)
        self.studio.layers.set_level(self.mid, 2)
        self.assertEqual(before, self.studio.snapshot())
        self.assertTrue(self.studio.layers.dirty)
        settings = self.studio.layers.view(self.mid)
        self.assertFalse(settings["visible"]["Terrain"])
        self.assertFalse(settings["visible"]["Unités"])
        self.assertEqual(settings["opacity"]["Décors"], 35)
        self.assertEqual(settings["active_level"], 2)
        self.assertTrue(settings["visible"]["Décors"])

    def test_locked_domains_reject_covered_edits_atomically(self):
        self.studio.layers.set_locked(self.mid, "Terrain", True)
        before = self.studio.snapshot()
        with self.assertRaises(AuthoringError):
            self.studio.paint([(2, 2)], "surface:water")
        self.assertEqual(before, self.studio.snapshot())
        # An unrelated layer is editable while terrain is locked.
        self.studio.paint([(3, 3)], "goal")
        self.assertIn([3, 3], self.studio.mission()["goal"])
        self.studio.layers.set_locked(self.mid, "Objectifs", True)
        before = self.studio.snapshot()
        with self.assertRaises(AuthoringError):
            self.studio.paint([(4, 4)], "goal")
        self.assertEqual(before, self.studio.snapshot())
        # Undo/redo are historical restores, not fresh editing commands.
        self.studio.undo()
        self.assertNotIn([3, 3], self.studio.mission()["goal"])
        self.studio.redo()
        self.assertIn([3, 3], self.studio.mission()["goal"])

    def test_decoration_lock_does_not_block_surface(self):
        self.studio.layers.set_locked(self.mid, "Décors", True)
        self.studio.paint([(2, 2)], "surface:stone")
        before = self.studio.snapshot()
        with self.assertRaises(AuthoringError):
            self.studio.paint([(2, 2)], "feature:tree")
        self.assertEqual(before, self.studio.snapshot())

    def test_structure_lock(self):
        self.studio.layers.set_locked(self.mid, "Bâtiments", True)
        before = self.studio.snapshot()
        with self.assertRaises(AuthoringError):
            self.studio.structure("Maison", (5, 5))
        self.assertEqual(before, self.studio.snapshot())
        self.studio.layers.set_locked(self.mid, "Bâtiments", False)
        self.studio.structure("Maison", (5, 5))
        self.assertEqual(len(self.studio.mission().get("structures", [])), 1)

    def test_mission_specific_and_sidecar_round_trip(self):
        self.studio.layers.set_visible(self.mid, "Terrain", False)
        self.studio.layers.set_locked(self.mid, "Terrain", True)
        self.studio.layers.set_level(self.mid, 3)
        self.studio.layers.set_opacity(self.mid, "Terrain", 45)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "jeanne.json"
            self.studio.save_as(path)
            self.assertTrue(view_sidecar_path(path).exists())
            old = load_views(path)
            self.assertIn(self.mid, old["missions"])
            self.assertFalse(self.studio.layers.dirty)
            new = MapStudio.open(path)
            new.select_map(self.mid)
            state = new.layers.view(self.mid)
            self.assertFalse(state["visible"]["Terrain"])
            self.assertTrue(state["locked"]["Terrain"])
            self.assertEqual(state["active_level"], 3)
            # v1 sidecar never silently persists an unversioned opacity key.
            self.assertEqual(state["opacity"]["Terrain"], 100)
            self.assertTrue(new.layers.view(new.map_ids()[0])["visible"]["Terrain"])
            self.assertEqual(new.mission(), self.studio.mission())
            self.assertEqual(self.studio.snapshot()["content"], new.snapshot()["content"])
            new.layers.set_locked(self.mid, "Terrain", False)
            self.assertTrue(new.layers.dirty)
            new.save()
            reopened = MapStudio.open(path)
            reopened.select_map(self.mid)
            self.assertFalse(reopened.layers.view(self.mid)["locked"]["Terrain"])

    def test_discard_and_validate_editor_only_controls(self):
        self.studio.layers.set_locked(self.mid, "Objets", True)
        self.studio.layers.discard()
        self.assertFalse(self.studio.layers.view(self.mid)["locked"]["Objets"])
        for layer in ("not-a-layer", "", None):
            with self.assertRaises(RuleError):
                self.studio.layers.set_visible(self.mid, layer, True)
        for value in (-1, 101, True, "50"):
            with self.assertRaises(RuleError):
                self.studio.layers.set_opacity(self.mid, "Terrain", value)
        for value in (-1, 4, True, "2"):
            with self.assertRaises(RuleError):
                self.studio.layers.set_level(self.mid, value)

    def test_external_sidecar_revision_is_not_overwritten(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "jeanne.json"
            self.studio.save_as(path)
            opened = MapStudio.open(path)
            opened.select_map(self.mid)
            opened.layers.set_visible(self.mid, "Terrain", False)
            original_content = path.read_bytes()
            sidecar = view_sidecar_path(path)
            outside_change = sidecar.read_bytes() + b" "
            sidecar.write_bytes(outside_change)
            with self.assertRaises(RuleError):
                opened.save()
            self.assertEqual(sidecar.read_bytes(), outside_change)
            self.assertEqual(path.read_bytes(), original_content)

    def test_save_as_rejects_existing_sidecar_without_writing_project(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "new_project.json"
            sidecar = view_sidecar_path(path)
            sidecar.write_text("Existing sidecar", encoding="utf-8")
            with self.assertRaises(RuleError):
                self.studio.save_as(path)
            self.assertFalse(path.exists())
            self.assertFalse(path.with_suffix(".game.json").exists())
            self.assertEqual(sidecar.read_text(encoding="utf-8"), "Existing sidecar")

    def test_undo_deleted_mission_repairs_selection(self):
        self.assertEqual(self.studio.mission_id, self.mid)
        self.studio.undo()  # Undo create
        self.assertNotIn(self.mid, self.studio.map_ids())
        self.assertIn(self.studio.mission_id, self.studio.map_ids())


if __name__ == "__main__":
    unittest.main()
