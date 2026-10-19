"""R38.2: safe prefab variant inheritance, place/update/undo and provenance."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project
from sporebound.authoring import add_blank_mission
from sporebound.editor_groups import create_editor_group
from sporebound.group_prefabs import capture_group_prefab
from sporebound.model import Content, RuleError
from sporebound.game_project import GameProject
from sporebound.prefab_variants import (
    KIND, NAMESPACE, VERSION, prefab_digest, preview_place_variant,
    preview_register_variant, preview_update_variant,
    preview_override_instance, resolve_variant, validate_variant,
)


def setup():
    content, project = reference_project()
    data = content.to_dict()
    source = next(m["id"] for m in data["missions"])
    data = add_blank_mission(data, "variant_target", "Variant target", 32, 32)
    data = create_editor_group(data, source, "Mechanics",
                               cells=((2, 4), (3, 4)))
    base = capture_group_prefab(data, source, ("group_1",), "Gate assembly")
    content = Content.from_dict(data)
    project = GameProject.default(content)
    return AuthoringSession.new(content, project), base


def descriptor(base, name="Fortified", group_name="Stone Gate"):
    return {"kind": KIND, "version": VERSION, "id": name,
            "base_sha256": prefab_digest(base),
            "overrides": [{"section": "groups", "id": base["groups"][0]["id"],
                           "field": "name", "value": group_name}]}


def placed_group(session, instance_id):
    pair = session.snapshot().to_dict()
    catalog = pair["project"]["extensions"][NAMESPACE]["data"]
    record = next(row for row in catalog["instances"] if row["id"] == instance_id)
    name = record["mapping"]["groups"][next(iter(record["mapping"]["groups"]))]
    mission = next(m for m in pair["content"]["missions"]
                   if m["id"] == record["mission_id"])
    return next(row for row in mission["editor_groups"] if row["id"] == name)


class PrefabVariantTests(unittest.TestCase):
    def test_register_preview_place_and_undo_are_atomic(self):
        session, source = setup()
        variant = descriptor(source)
        before = session.snapshot().to_dict()
        pending = preview_register_variant(session, source, variant)
        self.assertEqual(session.snapshot().to_dict(), before)
        session.apply(pending)
        self.assertEqual(session.revision, 1)
        self.assertIn(NAMESPACE, session.snapshot().to_dict()["project"]["extensions"])
        plan = preview_place_variant(session, source, variant["id"],
                                     "variant_target", (10, 12), "gateA")
        self.assertEqual(session.revision, 1)
        session.apply(plan)
        self.assertEqual(placed_group(session, "gateA")["name"], "Stone Gate")
        manifest = session.snapshot().to_dict()["project"]["extensions"][NAMESPACE]
        self.assertEqual(manifest["references"],
                         [{"kind": "mission", "id": "variant_target"}])
        self.assertEqual(len(manifest["data"]["instances"]), 1)
        session.undo()
        self.assertEqual(len(session.snapshot().to_dict()["project"]
                             ["extensions"][NAMESPACE]["data"]["instances"]), 0)
        session.redo()
        self.assertEqual(placed_group(session, "gateA")["name"], "Stone Gate")

    def test_inherited_updates_preserve_instance_overrides(self):
        session, source = setup()
        session.apply(preview_register_variant(session, source, descriptor(source)))
        session.apply(preview_place_variant(session, source, "Fortified",
                                            "variant_target", (10, 12), "gateA"))
        chosen = [{"section": "groups", "id": source["groups"][0]["id"],
                   "field": "name", "value": "Personal Gate"}]
        session.apply(preview_place_variant(session, source, "Fortified",
                                            "variant_target", (18, 12), "gateB",
                                            overrides=chosen))
        self.assertEqual(placed_group(session, "gateB")["name"], "Personal Gate")
        new = descriptor(source, group_name="Bronze Gate")
        proposal = preview_update_variant(session, source, new)
        self.assertEqual(placed_group(session, "gateA")["name"], "Stone Gate")
        session.apply(proposal)
        self.assertEqual(placed_group(session, "gateA")["name"], "Bronze Gate")
        self.assertEqual(placed_group(session, "gateB")["name"], "Personal Gate")
        session.undo()
        self.assertEqual(placed_group(session, "gateA")["name"], "Stone Gate")
        self.assertEqual(placed_group(session, "gateB")["name"], "Personal Gate")

    def test_direct_edits_conflict_and_never_disappear(self):
        session, source = setup()
        session.apply(preview_register_variant(session, source, descriptor(source)))
        session.apply(preview_place_variant(session, source, "Fortified",
                                            "variant_target", (10, 12), "gateA"))
        selected = placed_group(session, "gateA")["id"]

        def edit(content, project):
            row = next(m for m in content["missions"] if m["id"] == "variant_target")
            next(g for g in row["editor_groups"] if g["id"] == selected)["name"] = "My edit"
            return content, project

        session.apply(session.preview_pair(edit))
        before = session.snapshot().to_dict()
        with self.assertRaises(AuthoringError):
            preview_update_variant(session, source,
                                   descriptor(source, group_name="Other Gate"))
        self.assertEqual(session.snapshot().to_dict(), before)
        self.assertEqual(placed_group(session, "gateA")["name"], "My edit")

    def test_explicit_instance_override_and_stale_revision(self):
        session, source = setup()
        session.apply(preview_register_variant(session, source, descriptor(source)))
        place = preview_place_variant(session, source, "Fortified",
                                     "variant_target", (10, 12), "gateA")
        session.apply(place)
        item = {"section": "groups", "id": source["groups"][0]["id"],
                "field": "name", "value": "Local Gate"}
        proposal = preview_override_instance(session, source, "gateA", [item])
        self.assertEqual(placed_group(session, "gateA")["name"], "Stone Gate")
        session.apply(proposal)
        self.assertEqual(placed_group(session, "gateA")["name"], "Local Gate")
        updated = preview_update_variant(
            session, source, descriptor(source, group_name="Bronze Gate"))
        session.undo()
        with self.assertRaises(AuthoringError) as error:
            session.apply(updated)
        self.assertEqual(error.exception.code, "stale_revision")

    def test_schema_source_mismatch_and_corruption_fail_closed(self):
        session, source = setup()
        variant = descriptor(source)
        wrong = deepcopy(source)
        wrong["name"] = "Different source"
        with self.assertRaises(RuleError):
            resolve_variant(wrong, variant)
        invalid = deepcopy(variant)
        invalid["overrides"][0]["field"] = "id"
        with self.assertRaises(RuleError):
            validate_variant(source, invalid)
        invalid = deepcopy(variant)
        invalid["overrides"][0]["value"] = 4
        with self.assertRaises(RuleError):
            validate_variant(source, invalid)
        session.apply(preview_register_variant(session, source, variant))
        baseline = session.snapshot().to_dict()
        with self.assertRaises(AuthoringError):
            preview_place_variant(session, wrong, "Fortified",
                                  "variant_target", (10, 12), "bad")
        self.assertEqual(session.snapshot().to_dict(), baseline)
        broken = deepcopy(baseline["project"])
        broken["extensions"][NAMESPACE]["data"]["variants"][0]["version"] = 99
        with self.assertRaises(RuleError):
            GameProject.from_dict(broken, Content.from_dict(baseline["content"]))

    def test_no_qt_dependency(self):
        script = """
import sys
class Guard:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('PySide6', 'tkinter'):
            raise AssertionError('unexpected UI import')
sys.meta_path.insert(0, Guard())
from sporebound.prefab_variants import prefab_digest
assert callable(prefab_digest)
"""
        subprocess.run([sys.executable, "-c", script], check=True,
                       capture_output=True, text=True)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 missing")
class PrefabVariantQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_reads_current_project_and_r1_snapshot(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        from drawtemp.studio.r38_prefabs_qt import PrefabVariantsDialog
        session, source = setup()
        with tempfile.TemporaryDirectory() as folder:
            window = StudioWindow(session, settings=QSettings(
                str(Path(folder) / "studio.ini"), QSettings.IniFormat))
            self.assertIn("r38_prefabs", window.commands)
            dialog = PrefabVariantsDialog(window)
            dialog.use_source(source)
            dialog.variant_id.setText("Fortified")
            dialog.group_title.setText("Stone Gate")
            dialog.register()
            self.assertEqual(session.revision, 1)
            self.assertEqual(dialog.variant_list.count(), 1)
            dialog.mission.setCurrentIndex(dialog.mission.findData("variant_target"))
            dialog.anchor_x.setValue(10)
            dialog.anchor_y.setValue(12)
            dialog.instance_id.setText("gateA")
            dialog.place()
            self.assertEqual(placed_group(session, "gateA")["name"], "Stone Gate")
            window.close()


if __name__ == "__main__":
    unittest.main()
