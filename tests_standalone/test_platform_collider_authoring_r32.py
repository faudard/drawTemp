"""R32.C authoring acceptance: canonical extension, preview/apply, Undo/Redo.

Tests real Content/GameProject validators and the existing R1 studio history.
"""
from copy import deepcopy
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.platform_collider_authoring import (
    ColliderAuthoringError, PlatformColliderStudio,
)
from sporebound.game_project import GameProject
from sporebound.physics_scenes import EXTENSION
from sporebound.platform_physics import PhysicsError, PlatformPhysics


def collider(identifier="sensor", *, rect=None, trigger=True):
    return {
        "id": identifier,
        "rect": rect or [2500, 4000, 500, 500],
        "layer": 1, "mask": 1, "trigger": trigger, "one_way": False,
    }


class PlatformColliderAuthoringR32Tests(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.content = content
        self.session = AuthoringSession.new(content, project)
        self.author = PlatformColliderStudio(self.session)
        self.scene_id = "arrival"

    def _project(self):
        return self.session.snapshot().to_dict()["project"]

    def _create(self):
        plan = self.author.preview_create(
            self.scene_id, revision=self.session.revision)
        return self.author.apply(plan)

    def test_legacy_document_stays_byte_equivalent_until_apply(self):
        original = self._project()
        self.assertNotIn("extensions", original)
        plan = self.author.preview_create(self.scene_id,
                                          revision=self.session.revision)
        self.assertEqual(original, self._project())
        self.assertEqual(plan.source_revision, self.session.revision)
        self.assertIn(self.scene_id, self.author.targets())
        self.author.apply(plan)
        self.assertIn(EXTENSION, self._project()["extensions"])
        self.session.undo()
        self.assertEqual(self._project(), original)
        self.session.redo()
        self.assertIn(EXTENSION, self._project()["extensions"])

    def test_apply_single_undo_and_audited_gameproject_roundtrip(self):
        self._create()
        revision = self.session.revision
        pending = self.author.preview_put(
            self.scene_id, collider(), revision=revision)
        self.assertEqual(len(self.author.scene(self.scene_id)["colliders"]), 1)
        self.author.apply(pending)
        new = self.author.scene(self.scene_id)
        self.assertEqual(len(new["colliders"]), 2)
        model = GameProject.from_dict(self._project(), self.content)
        self.assertEqual(model.to_dict(), self._project())
        game = self.author.preview_playtest(self.scene_id)
        self.assertIsInstance(game, PlatformPhysics)
        game.step({"tick": 1, "move": 1})
        restored = PlatformPhysics.from_recording(game.recording(),
                                                  expected_scene=new)
        self.assertEqual(restored.digest(), game.digest())
        self.session.undo()
        self.assertEqual(len(self.author.scene(self.scene_id)["colliders"]), 1)
        self.session.redo()
        self.assertEqual(self.author.scene(self.scene_id), new)

    def test_stale_preview_and_external_changes_fail_without_mutation(self):
        self._create()
        stale = self.author.preview_put(
            self.scene_id, collider(), revision=self.session.revision)
        other = self.author.preview_put(
            self.scene_id, collider("second", rect=[3500, 3500, 400, 400]),
            revision=self.session.revision)
        self.author.apply(other)
        before = self._project()
        with self.assertRaises(AuthoringError):
            self.author.apply(stale)
        with self.assertRaises(ColliderAuthoringError):
            self.author.preview_put(self.scene_id, collider("other"),
                                    revision=0)
        self.assertEqual(before, self._project())

    def test_bad_colliders_and_scene_identity_are_rejected_on_project_load(self):
        self._create()
        before = self._project()
        bad = [
            collider("outside", rect=[12999, 4000, 1, 10]),
            collider("inside_actor", rect=[1010, 4250, 100, 200]),
            {**collider("wrong_mask"), "mask": True},
            {**collider("bad_oneway"), "one_way": True},
        ]
        for row in bad:
            with self.subTest(row=row), self.assertRaises(AuthoringError):
                self.author.preview_put(self.scene_id, row,
                                        revision=self.session.revision)
            self.assertEqual(before, self._project())
        poisoned = deepcopy(before)
        poisoned["extensions"][EXTENSION]["data"]["scenes"]["unknown"] = (
            poisoned["extensions"][EXTENSION]["data"]["scenes"].pop(self.scene_id))
        with self.assertRaises(Exception):
            GameProject.from_dict(poisoned, self.content)
        poisoned = deepcopy(before)
        poisoned["extensions"][EXTENSION]["data"]["scenes"][self.scene_id]["hero"]["pos"][0] = -1
        with self.assertRaises(Exception):
            GameProject.from_dict(poisoned, self.content)

    def test_remove_collider_and_scene_restores_optional_legacy_schema(self):
        self._create()
        self.author.apply(self.author.preview_put(
            self.scene_id, collider(), revision=self.session.revision))
        snap = self._project()
        self.author.apply(self.author.preview_remove(
            self.scene_id, "sensor", revision=self.session.revision))
        self.assertEqual([c["id"] for c in self.author.scene(self.scene_id)["colliders"]],
                         ["floor"])
        self.session.undo()
        self.assertEqual(self._project(), snap)
        self.author.apply(self.author.preview_remove_scene(
            self.scene_id, revision=self.session.revision))
        self.assertNotIn("extensions", self._project())
        self.assertEqual(self._project(),
                         GameProject.from_dict(self._project(), self.content).to_dict())

    def test_undo_save_as_open_same_content_without_sidecar(self):
        self._create()
        self.author.apply(self.author.preview_put(
            self.scene_id, collider(), revision=self.session.revision))
        with TemporaryDirectory() as directory:
            output = Path(directory) / "authoring.content.json"
            paths = self.session.save_as(output)
            self.assertEqual(len(paths), 2)
            restored = AuthoringSession.open(output)
            self.assertEqual(restored.snapshot().to_dict()["project"], self._project())
            other = PlatformColliderStudio(restored)
            self.assertEqual(other.scene(self.scene_id),
                             self.author.scene(self.scene_id))
            self.assertEqual(len(list(Path(directory).glob("*"))), 2)

    def test_qt_widget_renders_real_editor_controls_if_qt_available(self):
        try:
            from PySide6.QtWidgets import QApplication
            from drawtemp.studio.platform_collider_qt import ColliderEditorPanel
        except ImportError:
            self.skipTest("PySide6 unavailable")
        app = QApplication.instance() or QApplication([])
        panel = ColliderEditorPanel(self.session)
        self.assertEqual(panel.objectName(), "r32-collider-editor")
        self.assertIsNotNone(panel.findChild(type(panel.create_button), "r32-create-scene"))
        panel.target.setCurrentIndex(panel.target.findData(self.scene_id))
        panel.create_button.click()
        self.assertTrue(panel.apply_button.isEnabled())
        self.assertNotIn("extensions", self._project())
        panel.apply_button.click()
        self.assertEqual(len(self.author.scene(self.scene_id)["colliders"]), 1)
        panel.identifier.setText("sensor")
        panel.preview_button.click()
        self.assertTrue(panel.apply_button.isEnabled())
        panel.apply_button.click()
        self.assertEqual(len(self.author.scene(self.scene_id)["colliders"]), 2)
        panel.close()
        del panel
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
