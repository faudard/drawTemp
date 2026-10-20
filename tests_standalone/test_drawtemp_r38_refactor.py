"""R38.3: revision-locked typed refactor of mission-scoped actor/object IDs."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import os
import tempfile
from pathlib import Path
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.logic_graph import preview_graph
from drawtemp.sdk.r38_refactor import (
    RefactorReview, preview_rename_identity, apply_rename_identity,
)
from drawtemp.sdk.reference import reference_project
from sporebound.authoring import add_blank_mission, add_object
from sporebound.event_composer import condition, action, save_event
from sporebound.model import Content
from sporebound.game_project import GameProject


def fixture():
    content, project = reference_project()
    return AuthoringSession.new(content, project), next(iter(content.missions))


def snapshot_mission(session, mid):
    return next(m for m in session.snapshot().to_dict()["content"]["missions"]
                if m["id"] == mid)


class RefactorTests(unittest.TestCase):
    def test_object_rename_updates_switch_and_native_r9_without_text_rewrite(self):
        session, mid = fixture()
        source = session.snapshot().to_dict()
        data = save_event(source["content"], mid, "open_the_door",
                          condition("interact", object_id="gate"),
                          [action("message", text="gate is a word in dialogue")])
        session.apply(session.preview_pair(
            lambda c, p: (data, p), kind="test.event"))
        before = session.snapshot().to_dict()
        review = preview_rename_identity(session, "objects", mid, "gate", "portcullis")
        self.assertIsInstance(review, RefactorReview)
        self.assertTrue(review.change_count >= 3)
        self.assertEqual(session.snapshot().to_dict(), before)
        paths = [row.path for row in review.changes]
        self.assertTrue(any("objects" in path for path in paths))
        self.assertTrue(any("triggers" in path for path in paths))
        self.assertEqual(len(paths), len(set(paths)))
        apply_rename_identity(session, review)
        mission = snapshot_mission(session, mid)
        self.assertIn("portcullis", {obj["id"] for obj in mission["objects"]})
        self.assertEqual(next(o for o in mission["objects"]
                              if o["id"] == "lever")["link"], "portcullis")
        event = next(e for e in mission["triggers"]
                     if e["id"] == "open_the_door")
        self.assertEqual(event["object"], "portcullis")
        self.assertEqual(event["actions"][0]["text"], "gate is a word in dialogue")
        session.undo()
        self.assertEqual(session.snapshot().to_dict()["content"], before["content"])
        session.redo()
        self.assertIn("portcullis", {o["id"] for o in snapshot_mission(session, mid)["objects"]})

    def test_scope_does_not_touch_identical_id_in_other_mission(self):
        session, mid = fixture()
        before = session.snapshot().to_dict()
        data = add_blank_mission(before["content"], "other_area", "Other area", 16, 16)
        data = add_object(data, "other_area", "gate", "door", (6, 6))
        project = GameProject.default(Content.from_dict(data))
        session = AuthoringSession.new(Content.from_dict(data), project)
        review = preview_rename_identity(session, "objects", mid, "gate", "newgate")
        session.apply(review.plan)
        self.assertIn("gate", {o["id"] for o in snapshot_mission(session, "other_area")["objects"]})
        self.assertIn("newgate", {o["id"] for o in snapshot_mission(session, mid)["objects"]})

    def test_actor_rename_updates_protected_id_and_group_membership(self):
        session, mid = fixture()
        before = session.snapshot().to_dict()
        actor_id = next(u["id"] for u in snapshot_mission(session, mid)["units"]
                        if u["team"] == "player")
        def add_linked(c, p):
            m = next(x for x in c["missions"] if x["id"] == mid)
            m["protected_id"] = actor_id
            m.setdefault("editor_groups", []).append({
                "id": "refactor_group", "name": "Group", "parent": None,
                "cells": [], "unit_ids": [actor_id], "object_ids": [],
                "structure_ids": [],
            })
            return c, p
        session.apply(session.preview_pair(add_linked, kind="test.link"))
        review = preview_rename_identity(session, "actors", mid,
                                         actor_id, "new_hero")
        self.assertGreaterEqual(review.change_count, 3)
        session.apply(review.plan)
        mission = snapshot_mission(session, mid)
        self.assertEqual(mission["protected_id"], "new_hero")
        self.assertIn("new_hero", mission["editor_groups"][0]["unit_ids"])
        self.assertIn("new_hero", {unit["id"] for unit in mission["units"]})
        self.assertNotIn(actor_id, {unit["id"] for unit in mission["units"]})

    def test_r31_graph_and_generated_event_remain_equal(self):
        session, mid = fixture()
        graph = {
            "schema_version": 1, "id": "gate_intro", "mission_id": mid,
            "entry": "enter", "nodes": [
                {"id": "enter", "kind": "event",
                 "params": {"kind": "interact", "object_id": "gate"}},
                {"id": "message", "kind": "action",
                 "params": {"kind": "message", "text": "gate remains prose"}},
            ],
            "edges": [{"from": "enter", "out": "next",
                       "to": "message", "in": "flow"}],
        }
        session.apply(preview_graph(session, graph))
        review = preview_rename_identity(session, "objects", mid, "gate", "gate_2")
        self.assertTrue(any("org.drawtemp.logic" in ch.path for ch in review.changes))
        session.apply(review.plan)
        from drawtemp.sdk.logic_graph import compile_r9_triggers
        pair = session.snapshot().to_dict()
        graph_after = pair["project"]["extensions"]["org.drawtemp.logic"]["data"]["graphs"][0]
        self.assertEqual(graph_after["nodes"][0]["params"]["object_id"], "gate_2")
        mission = snapshot_mission(session, mid)
        self.assertEqual(next(t for t in mission["triggers"]
                              if t["id"] == "r31_gate_intro"),
                         compile_r9_triggers(graph_after)[0])

    def test_r31_manual_native_divergence_blocks_refactor(self):
        session, mid = fixture()
        graph = {
            "schema_version": 1, "id": "gate_intro", "mission_id": mid,
            "entry": "enter", "nodes": [
                {"id": "enter", "kind": "event",
                 "params": {"kind": "interact", "object_id": "gate"}},
                {"id": "message", "kind": "action",
                 "params": {"kind": "message", "text": "initial"}},
            ],
            "edges": [{"from": "enter", "out": "next",
                       "to": "message", "in": "flow"}],
        }
        session.apply(preview_graph(session, graph))
        def native_edit(c, p):
            mission = next(m for m in c["missions"] if m["id"] == mid)
            next(t for t in mission["triggers"] if t["id"] == "r31_gate_intro")[
                "actions"][0]["text"] = "outside Studio"
            return c, p
        session.apply(session.preview_pair(native_edit))
        before = session.snapshot().to_dict()
        with self.assertRaises(AuthoringError):
            preview_rename_identity(session, "objects", mid, "gate", "gate_2")
        self.assertEqual(session.snapshot().to_dict(), before)

    def test_stale_preview_collision_and_unsupported_family(self):
        session, mid = fixture()
        with self.assertRaises(AuthoringError):
            preview_rename_identity(session, "objects", mid, "gate", "lever")
        with self.assertRaises(AuthoringError):
            preview_rename_identity(session, "maps", mid, mid, "other")
        review = preview_rename_identity(session, "objects", mid, "gate", "new_gate")
        session.apply(session.preview_pair(
            lambda c, p: (c, dict(p, title="Modified")), kind="test.change"))
        session.undo()
        with self.assertRaises(AuthoringError) as error:
            apply_rename_identity(session, review)
        self.assertEqual(error.exception.code, "stale_revision")
        self.assertIn("gate", {o["id"] for o in snapshot_mission(session, mid)["objects"]})


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 missing")
class RefactorQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_preview_and_apply_via_studio_dialog(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        from drawtemp.studio.r38_refactor_qt import RefactorDialog
        session, mid = fixture()
        with tempfile.TemporaryDirectory() as folder:
            owner = StudioWindow(session, settings=QSettings(
                str(Path(folder) / "studio.ini"), QSettings.IniFormat))
            self.assertIn("r38_refactor", owner.commands)
            dialog = RefactorDialog(owner)
            dialog.family.setCurrentIndex(dialog.family.findData("objects"))
            dialog.mission.setCurrentIndex(dialog.mission.findData(mid))
            dialog.old_id.setCurrentIndex(dialog.old_id.findData("gate"))
            dialog.new_id.setText("new_gate")
            self.assertTrue(dialog.preview())
            self.assertIn("gate", {o["id"] for o in snapshot_mission(session, mid)["objects"]})
            self.assertTrue(dialog.apply())
            self.assertIn("new_gate", {o["id"] for o in snapshot_mission(session, mid)["objects"]})
            owner.close()


if __name__ == "__main__":
    unittest.main()
