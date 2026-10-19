"""R44.B headless authoring and transactional correctness."""
from copy import deepcopy
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.studio.world_atlas_authoring import (
    default_world_atlas, preview_world_atlas, apply_world_atlas, assign_scene,
    edit_portal, edit_object, place_scene, set_region)
from sporebound.model import RuleError
from sporebound.world_graph44 import EXTENSION
from tests_standalone.test_r25_scene_router import scene_fixture


class WorldAtlasAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = scene_fixture()
        self.session = AuthoringSession.new(self.content, self.project)
        self.initial = self.session.snapshot().to_dict()
        self.atlas = default_world_atlas(self.session)

    def test_bootstrap_and_single_transaction_undo_redo(self):
        self.assertEqual(self.atlas["regions"][0]["scenes"][0]["id"], "arrival")
        before = deepcopy(self.initial)
        preview = preview_world_atlas(self.session, self.atlas, expected_revision=0)
        self.assertTrue(preview.report["changed"])
        self.assertEqual(preview.report["scenes"], 2)
        self.assertEqual(self.session.snapshot().to_dict(), before)
        apply_world_atlas(self.session, preview)
        saved = self.session.snapshot().to_dict()["project"]["extensions"][EXTENSION]["data"]
        self.assertEqual(saved, self.atlas)
        with self.assertRaises(AuthoringError):
            apply_world_atlas(self.session, preview)
        self.session.undo()
        self.assertNotIn(EXTENSION, self.session.snapshot().to_dict()["project"].get("extensions", {}))
        self.session.redo()
        self.assertEqual(self.session.snapshot().to_dict()["project"]["extensions"][EXTENSION]["data"],
                         self.atlas)

    def test_region_portal_geometry_object_and_one_undo(self):
        self.session.apply(preview_world_atlas(self.session, self.atlas).plan)
        original = self.session.snapshot().to_dict()
        atlas = assign_scene(self.atlas, "arrival", "lowlands")
        atlas = set_region(atlas, "lowlands", biome="forest", projection="isometric")
        atlas = place_scene(atlas, "arrival", [27, 34])
        atlas = edit_portal(atlas, "to_arena", travel_cost=8)
        atlas = edit_object(atlas, "arrival", "box", "chest", "world44_box_open")
        preview = preview_world_atlas(self.session, atlas, expected_revision=1)
        self.assertEqual(preview.report["regions"], 2)
        self.assertEqual(preview.report["objects"], 1)
        self.assertEqual(self.session.snapshot().to_dict(), original)
        apply_world_atlas(self.session, preview)
        saved = self.session.snapshot().to_dict()["project"]["extensions"][EXTENSION]["data"]
        self.assertEqual(saved, atlas)
        self.session.undo()
        self.assertEqual(self.session.snapshot().to_dict()["project"]["extensions"][EXTENSION]["data"],
                         self.atlas)

    def test_single_scene_no_outbound_portal(self):
        # Canonical R25 accepts a one-scene graph with zero links.
        content, project = scene_fixture()
        project.scene_routes["links"] = []
        project.validate(content)
        editor = AuthoringSession.new(content, project)
        draft = default_world_atlas(editor)
        self.assertEqual(draft["portals"], [])
        self.assertEqual(len(draft["regions"][0]["scenes"]), 1)
        apply_world_atlas(editor, preview_world_atlas(editor, draft))
        self.assertEqual(editor.revision, 1)

    def test_existing_envelope_references_are_not_silently_dropped(self):
        # A changed envelope is a transaction even when its data match.
        self.session.apply(preview_world_atlas(self.session, self.atlas).plan)
        data = self.session.snapshot().to_dict()
        self.assertEqual(data["project"]["extensions"][EXTENSION]["schema_version"], 1)
        unchanged = preview_world_atlas(self.session, self.atlas)
        self.assertFalse(unchanged.report["changed"])
        with self.assertRaises(AuthoringError):
            apply_world_atlas(self.session, unchanged)

    def test_stale_preview_rejected_after_unrelated_edit(self):
        old = preview_world_atlas(self.session, self.atlas)
        revised = place_scene(self.atlas, "arrival", [20, 30])
        apply_world_atlas(self.session, preview_world_atlas(self.session, revised))
        with self.assertRaises(AuthoringError):
            apply_world_atlas(self.session, old)
        with self.assertRaises(RuleError):
            preview_world_atlas(self.session, self.atlas, expected_revision=0)

    def test_invalid_portal_is_atomic(self):
        snapshot = self.session.snapshot().to_dict()
        broken = edit_portal(self.atlas, "to_arena", travel_cost=True)
        with self.assertRaises(AuthoringError):
            preview_world_atlas(self.session, broken)
        absent = edit_portal(self.atlas, "to_arena", enabled=False)
        with self.assertRaises(AuthoringError):
            preview_world_atlas(self.session, absent)
        duplicate_flag = edit_object(self.atlas, "arrival", "a", "chest", "world44_same")
        duplicate_flag = edit_object(duplicate_flag, "arrival", "b", "door", "world44_same")
        with self.assertRaises(AuthoringError):
            preview_world_atlas(self.session, duplicate_flag)
        self.assertEqual(self.session.snapshot().to_dict(), snapshot)


if __name__ == "__main__":
    unittest.main()
