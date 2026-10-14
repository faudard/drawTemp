"""R1.B headless Qt-ready authoring: typed commands, revisions, history and disk."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import Content, GameProject
from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.sdk.simulation import Simulation
from sporebound.editor_architecture import EntityCommand


def rename_jeanne(name="Jeanne — éditée"):
    return EntityCommand("edit", "actor", "jeanne",
                         fields=(("name", name),))


class AuthoringSessionTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()
        self.studio = AuthoringSession.new(self.content, self.project)

    def test_snapshot_is_recursively_immutable_and_detached(self):
        snapshot = self.studio.snapshot()
        with self.assertRaises(FrozenInstanceError):
            snapshot.revision = 10
        with self.assertRaises(TypeError):
            snapshot.project["title"] = "poison"
        with self.assertRaises(TypeError):
            snapshot.content["missions"][0]["units"][0]["name"] = "poison"
        detached = snapshot.to_dict()
        json.dumps(detached)
        detached["content"]["missions"][0]["units"][0]["name"] = "poison"
        self.assertNotEqual(self.studio.snapshot().content["missions"][0]["units"][0]["name"],
                            "poison")
        self.assertFalse(snapshot.dirty)

    def test_real_canonical_entity_command_is_transactional(self):
        initial = self.studio.snapshot()
        plan = self.studio.preview(rename_jeanne(), MISSION)
        self.assertEqual(plan.source_revision, initial.revision)
        self.assertEqual(self.studio.snapshot(), initial)
        result = self.studio.apply(plan)
        self.assertEqual(result.kind, "entity")
        self.assertEqual(result.mission_id, MISSION)
        self.assertEqual(result.source_revision, 0)
        self.assertEqual(result.snapshot.revision, 1)
        self.assertTrue(result.snapshot.dirty)
        self.assertTrue(result.snapshot.can_undo)
        self.assertEqual(result.snapshot.content["missions"][0]["units"][0]["name"],
                         "Jeanne — éditée")
        undo = self.studio.undo().snapshot
        self.assertEqual(undo.content, initial.content)
        self.assertEqual(undo.project, initial.project)
        self.assertTrue(undo.can_redo)
        redo = self.studio.redo().snapshot
        self.assertEqual(redo.content, result.snapshot.content)

    def test_stale_and_foreign_plans_rejected_even_after_undo_aba(self):
        stale = self.studio.preview(rename_jeanne(), MISSION)
        foreign = AuthoringSession.new(self.content, self.project)
        with self.assertRaises(AuthoringError) as error:
            foreign.apply(stale)
        self.assertEqual(error.exception.code, "foreign_preview")
        self.studio.apply(stale)
        self.studio.undo()
        self.assertEqual(self.studio.snapshot().content,
                         AuthoringSession.new(self.content, self.project).snapshot().content)
        with self.assertRaises(AuthoringError) as error:
            self.studio.apply(stale)
        self.assertEqual(error.exception.code, "stale_revision")
        self.assertEqual(self.studio.revision, 2)

    def test_rejected_commands_leave_documents_and_history_unchanged(self):
        baseline = self.studio.snapshot()
        with self.assertRaises(AuthoringError) as error:
            self.studio.preview(rename_jeanne(""), MISSION)
        self.assertEqual(error.exception.code, "invalid_edit")
        self.assertEqual(self.studio.snapshot(), baseline)
        with self.assertRaises(AuthoringError) as error:
            self.studio.preview(rename_jeanne(), "missing")
        self.assertEqual(error.exception.code, "unknown_mission")
        self.assertEqual(self.studio.snapshot(), baseline)
        with self.assertRaises(AuthoringError) as error:
            self.studio.apply(self.studio.preview(rename_jeanne("Jeanne"), MISSION))
        self.assertEqual(error.exception.code, "unchanged")
        self.assertEqual(self.studio.snapshot(), baseline)

    def test_project_only_edit_is_validated_and_undoable(self):
        plan = self.studio.preview_project(
            lambda project: {**project, "title": "Jeanne — Director Cut"})
        result = self.studio.apply(plan)
        self.assertEqual(result.snapshot.project["title"], "Jeanne — Director Cut")
        self.assertEqual(result.views, ("workspace", "inspector"))
        self.assertEqual(self.studio.undo().snapshot.project["title"],
                         self.project.title)
        with self.assertRaises(AuthoringError):
            self.studio.preview_project(lambda project: {**project, "title": ""})

    def test_content_and_project_commit_once_with_single_undo(self):
        def pair(content, project):
            content = deepcopy(content)
            project = deepcopy(project)
            content["missions"][0]["name"] = "Village 5.0"
            project["title"] = "DrawTemp 5.0"
            return content, project

        result = self.studio.apply(
            self.studio.preview_pair(pair, kind="map-and-project", mission_id=MISSION))
        self.assertEqual(result.snapshot.content["missions"][0]["name"], "Village 5.0")
        self.assertEqual(result.snapshot.project["title"], "DrawTemp 5.0")
        before = self.studio.undo().snapshot
        self.assertEqual(before.content["missions"][0]["name"],
                         self.content.to_dict()["missions"][0]["name"])
        self.assertEqual(before.project["title"], self.project.title)
        self.assertFalse(before.can_undo)

    def test_canonical_save_open_modify_reload_and_simulation(self):
        with TemporaryDirectory() as directory:
            content_path = Path(directory) / "jeanne.json"
            self.studio.save_as(content_path)
            self.assertFalse(self.studio.snapshot().dirty)
            self.assertTrue(content_path.is_file())
            self.assertTrue(content_path.with_suffix(".game.json").is_file())
            loaded = AuthoringSession.open(content_path)
            self.assertEqual(loaded.snapshot().content, self.studio.snapshot().content)
            loaded.execute(rename_jeanne(), MISSION)
            self.assertTrue(loaded.snapshot().dirty)
            loaded.save()
            self.assertFalse(loaded.snapshot().dirty)
            reopened = AuthoringSession.open(content_path)
            exported = reopened.snapshot().to_dict()
            content = Content.from_dict(exported["content"])
            project = GameProject.from_dict(exported["project"], content)
            game = Simulation.new(content, project, "main")
            game.choose_story_option("enter")
            game.start_mission(MISSION)
            game.execute({"kind": "interact", "unit": "jeanne", "object": "lever"})
            self.assertEqual(game.simulate(max_steps=700).battle["result"], "victory")

    def test_external_file_change_is_not_overwritten(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "jeanne.json"
            self.studio.save_as(path)
            self.studio.execute(rename_jeanne(), MISSION)
            altered = path.read_bytes() + b" "
            path.write_bytes(altered)
            with self.assertRaises(AuthoringError) as error:
                self.studio.save()
            self.assertEqual(error.exception.code, "save_failed")
            self.assertEqual(path.read_bytes(), altered)
            self.assertTrue(self.studio.snapshot().dirty)

    def test_save_as_refuses_to_overwrite_even_one_document(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "jeanne.json"
            path.write_text("Existing work", encoding="utf-8")
            with self.assertRaises(AuthoringError) as error:
                self.studio.save_as(path)
            self.assertEqual(error.exception.code, "destination_exists")
            self.assertEqual(path.read_text(encoding="utf-8"), "Existing work")

    def test_interrupted_two_document_save_requires_explicit_recovery(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "jeanne.json"
            self.studio.save_as(path)
            self.studio.execute(rename_jeanne(), MISSION)
            store = self.studio._store
            publish = store._publish_one

            def interrupted(target):
                if target == store.project_path:
                    raise OSError("simulated crash after first document")
                publish(target)

            store._publish_one = interrupted
            with self.assertRaises(AuthoringError):
                self.studio.save()
            self.assertTrue(store.pending)
            with self.assertRaises(AuthoringError) as error:
                AuthoringSession.open(path)
            self.assertEqual(error.exception.code, "recovery_required")
            recovered = AuthoringSession.recover(path, "complete")
            self.assertFalse(store.pending)
            self.assertEqual(recovered.snapshot().content["missions"][0]["units"][0]["name"],
                             "Jeanne — éditée")
            self.assertFalse(recovered.snapshot().dirty)

    def test_headless_imports_under_graphics_blocker(self):
        source = """import sys
class Block:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('tkinter', '_tkinter', 'PySide6', 'PyQt6'):
            raise AssertionError(fullname)
sys.meta_path.insert(0, Block())
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.sdk.authoring import AuthoringSession
from sporebound.editor_architecture import EntityCommand
content, project = reference_project()
studio = AuthoringSession.new(content, project)
command = EntityCommand('edit', 'actor', 'jeanne', fields=(('name', 'Jeanne Qt'),))
studio.apply(studio.preview(command, MISSION))
assert studio.snapshot().content['missions'][0]['units'][0]['name'] == 'Jeanne Qt'
"""
        subprocess.run([sys.executable, "-c", source], check=True, capture_output=True,
                       text=True, cwd=Path(__file__).resolve().parents[1])


if __name__ == "__main__":
    unittest.main()
