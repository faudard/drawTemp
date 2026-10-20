"""R51.A headless contract, authoring atomicity, and legacy/CT regression."""
from copy import deepcopy
import json
import unittest

from drawtemp.sdk.authoring import AuthoringSession, AuthoringError
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.r51_layout_authoring import LayoutAuthoring, LayoutAuthoringError
from sporebound.engine import Battle
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.presentation import battle_frame
from sporebound.ui_layout_r51 import (
    NAMESPACE, UiLayoutError, catalog_from_project, project_layout,
    validate_ui_catalog,
)


def sample_layout():
    return {
        "kind": "HUD_CT",
        "root": {
            "id": "main", "type": "column", "children": [
                {"id": "scene", "type": "text",
                 "binding": {"path": "session.scene_id", "type": "str"}},
                {"id": "hp", "type": "gauge",
                 "binding": {"path": "combat.active_hp", "type": "int"},
                 "max_binding": {"path": "combat.active_max_hp", "type": "int"}},
                {"id": "end_turn", "type": "button", "text": "Fin du tour",
                 "action": "combat.end_turn"},
            ],
        },
        "breakpoints": [
            {"min_width": 0, "columns": 1},
            {"min_width": 900, "columns": 2},
        ],
        "focus_order": ["end_turn"],
    }


class DeclarativeUiTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()
        self.editor = AuthoringSession.new(self.content, self.project)
        self.layouts = LayoutAuthoring(self.editor)

    def test_legacy_project_and_session_stay_unchanged(self):
        original = self.project.to_dict()
        before = GameSession.new(self.content, self.project, "main", seed=17).recording()
        self.assertNotIn("extensions", original)
        self.assertEqual(catalog_from_project(self.project),
                         {"version": 1, "layouts": {}})
        restored = GameProject.from_dict(original, self.content)
        self.assertEqual(restored.to_dict(), original)
        self.assertEqual(GameSession.new(
            self.content, restored, "main", seed=17).recording(), before)

    def test_canonical_roundtrip_and_replay_safe(self):
        layout = sample_layout()
        original = self.editor.snapshot().to_dict()
        preview = self.layouts.preview_replace("battle_hud", layout, expected_revision=0)
        self.assertEqual(self.editor.revision, 0)
        self.assertEqual(self.editor.snapshot().to_dict(), original)
        self.layouts.apply(preview)
        state = self.editor.snapshot().to_dict()
        self.assertEqual(state["content"], original["content"])
        project = GameProject.from_dict(
            json.loads(json.dumps(state["project"])), self.content)
        self.assertEqual(project.to_dict(), state["project"])
        self.assertEqual(project.extensions[NAMESPACE]["schema_version"], 1)
        self.assertEqual(catalog_from_project(project)["layouts"]["battle_hud"], layout)
        session = GameSession.new(self.content, project, "main", seed=7)
        recording = session.recording()
        self.assertEqual(
            GameSession.from_recording(recording, self.content, project).recording(),
            recording)

    def test_authoring_is_one_undo_step_and_stale_preview_fails(self):
        first = self.layouts.preview_replace("battle_hud", sample_layout())
        second = self.layouts.preview_replace("alternative", {
            **sample_layout(), "kind": "HUD_ACTION",
        })
        self.layouts.apply(first)
        with self.assertRaises(AuthoringError):
            self.layouts.apply(second)
        with self.assertRaises(LayoutAuthoringError):
            self.layouts.preview_remove("battle_hud", expected_revision=0)
        self.editor.undo()
        self.assertNotIn("extensions", self.editor.snapshot().to_dict()["project"])
        self.editor.redo()
        self.assertIn(NAMESPACE,
                      self.editor.snapshot().to_dict()["project"]["extensions"])
        self.layouts.apply(self.layouts.preview_remove(
            "battle_hud", expected_revision=self.editor.revision))
        self.assertNotIn("extensions", self.editor.snapshot().to_dict()["project"])
        self.editor.undo()
        self.assertIn(NAMESPACE,
                      self.editor.snapshot().to_dict()["project"]["extensions"])

    def test_read_only_breakpoints_and_ct_bindings(self):
        self.layouts.apply(self.layouts.preview_replace("battle_hud", sample_layout()))
        project = GameProject.from_dict(
            self.editor.snapshot().to_dict()["project"], self.content)
        session = GameSession.new(self.content, project, "main", seed=12)
        battle = Battle(self.content, MISSION, seed=9)
        frame = battle_frame(battle)
        before_session = session.recording()
        before_battle = battle.digest()
        catalog = catalog_from_project(project)
        compact = project_layout("battle_hud", catalog, session,
                                 width=600, battle_frame=frame)
        wide = project_layout("battle_hud", catalog, session,
                              width=1200, battle_frame=frame)
        self.assertEqual((compact["columns"], wide["columns"]), (1, 2))
        self.assertEqual(compact["root"]["children"][0]["value"], session.route_scene or "")
        actor = next(a for a in frame.actors if a.id == frame.active_id)
        self.assertEqual(compact["root"]["children"][1]["value"], actor.hp)
        self.assertEqual(compact["root"]["children"][1]["max_value"], actor.max_hp)
        compact["root"]["children"][1]["value"] = -999
        self.assertEqual(
            project_layout("battle_hud", catalog, session,
                           width=600, battle_frame=frame)["root"]["children"][1]["value"],
            actor.hp)
        self.assertEqual(session.recording(), before_session)
        self.assertEqual(battle.digest(), before_battle)
        with self.assertRaises(UiLayoutError):
            project_layout("battle_hud", catalog, session, width=600)
        with self.assertRaises(UiLayoutError):
            project_layout("battle_hud", catalog, session,
                           width=True, battle_frame=frame)

    def test_invalid_documents_fail_closed_at_project_validation(self):
        good = {"version": 1, "layouts": {"battle_hud": sample_layout()}}
        broken = []
        x = deepcopy(good); x["version"] = True; broken.append(x)
        x = deepcopy(good); x["layouts"]["battle_hud"]["kind"] = "QML"; broken.append(x)
        x = deepcopy(good); x["layouts"]["battle_hud"]["root"]["children"][0]["binding"]["path"] = "__class__"; broken.append(x)
        x = deepcopy(good); x["layouts"]["battle_hud"]["root"]["children"][0]["binding"]["type"] = "int"; broken.append(x)
        x = deepcopy(good); x["layouts"]["battle_hud"]["root"]["children"][1]["type"] = "code"; broken.append(x)
        x = deepcopy(good); x["layouts"]["battle_hud"]["root"]["children"][2]["action"] = "eval(script)"; broken.append(x)
        x = deepcopy(good); x["layouts"]["battle_hud"]["root"]["children"][2]["id"] = "hp"; broken.append(x)
        x = deepcopy(good); x["layouts"]["battle_hud"]["focus_order"] = []; broken.append(x)
        x = deepcopy(good); x["layouts"]["battle_hud"]["breakpoints"][1]["min_width"] = 0; broken.append(x)
        x = deepcopy(good); x["layouts"]["battle_hud"]["breakpoints"][0]["columns"] = True; broken.append(x)
        x = deepcopy(good); x["layouts"]["battle_hud"]["root"]["unexpected"] = True; broken.append(x)
        x = deepcopy(good); x["layouts"]["bad/name"] = x["layouts"].pop("battle_hud"); broken.append(x)
        x = deepcopy(good); x["layouts"]["battle_hud"]["root"]["children"][1]["max_binding"]["path"] = "session.scene_id"; broken.append(x)
        for index, payload in enumerate(broken):
            with self.subTest(case=index):
                with self.assertRaises(UiLayoutError):
                    validate_ui_catalog(payload)
                project = deepcopy(self.project)
                project.extensions[NAMESPACE] = {
                    "schema_version": 1, "data": payload}
                with self.assertRaises(UiLayoutError):
                    project.validate(self.content)

    def test_explicit_version_and_missing_layout_rejected(self):
        with self.assertRaises(UiLayoutError):
            validate_ui_catalog({"version": 2, "layouts": {}})
        with self.assertRaises(UiLayoutError):
            validate_ui_catalog({"version": 1, "layouts": [], "extra": 0})
        session = GameSession.new(self.content, self.project, "main")
        with self.assertRaises(UiLayoutError):
            project_layout("unknown", {"version": 1, "layouts": {}},
                           session, width=800)

    def test_projection_rejects_non_session_and_bad_layout_width(self):
        catalog = {"version": 1, "layouts": {"battle_hud": sample_layout()}}
        for width in (-1, 0, 16385, "800"):
            with self.subTest(width=width), self.assertRaises(UiLayoutError):
                project_layout("battle_hud", catalog, object(), width=width)
        with self.assertRaises(UiLayoutError):
            project_layout("battle_hud", catalog, object(), width=800)


if __name__ == "__main__":
    unittest.main()
