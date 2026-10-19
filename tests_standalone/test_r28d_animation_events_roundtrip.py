"""R28.D gates: asset-backed animation, R9 quest links, isolated GameSession replay."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.events import EventStudio
from drawtemp.studio.r28d_workflow import (
    AnimationHitboxStudio, EventQuestGraph, IsolatedPlaytest, R28DError,
)
from sporebound.assets import AssetRegistry
from sporebound.event_composer import action, condition
from sporebound.model import RuleError


def editor():
    return AuthoringSession.new(*reference_project())


class AnimationHitboxTests(unittest.TestCase):
    def test_legacy_manifest_and_footprint_preview_do_not_edit_jeanne(self):
        s = editor()
        before = s.snapshot().to_dict()
        tool = AnimationHitboxStudio(s)
        self.assertEqual(tool.manifest(), {
            "version": 1, "entries": [], "bindings": {}})
        self.assertEqual(tool.sprites(), ())
        report = tool.hitboxes(MISSION)
        self.assertFalse(report["editable"])
        self.assertTrue(report["units"])
        mission = before["content"]["missions"][0]
        expected = {u["id"]: u for u in mission["units"]}
        for unit in report["units"]:
            initial = expected[unit["id"]]
            self.assertIn(initial["pos"], unit["occupied_cells"])
            self.assertEqual(
                len(unit["occupied_cells"]),
                unit["footprint"][0] * unit["footprint"][1])
        self.assertEqual(s.snapshot().to_dict(), before)

    def test_register_sprite_and_animation_timeline_with_lookup_and_undo(self):
        s = editor()
        tool = AnimationHitboxStudio(s)
        baseline = s.snapshot().to_dict()
        first = tool.preview_sprite("hero_walk_0", "art/hero_walk_0.png")
        self.assertEqual(s.snapshot().to_dict(), baseline)
        tool.apply(first)
        tool.apply(tool.preview_sprite("hero_walk_1", "art/hero_walk_1.png"))
        revision = s.revision
        timeline = tool.preview_animation(
            "hero_move_anim", [
                {"sprite": "hero_walk_0", "duration_ms": 120},
                {"sprite": "hero_walk_1", "duration_ms": 80},
            ], loop=True, slot="hero_move")
        self.assertEqual(s.revision, revision)
        self.assertEqual(timeline.before["bindings"], {})
        self.assertEqual(timeline.after["bindings"]["animation"]["hero_move"],
                         "hero_move_anim")
        tool.apply(timeline)
        self.assertEqual(s.revision, revision + 1)
        self.assertEqual(tool.animations(), ("hero_move_anim",))
        self.assertEqual(tool.sample(
            "hero_move", 0, actor_id="hero", action="move")["sprite"],
            "hero_walk_0")
        self.assertEqual(tool.sample(
            "hero_move", 130, actor_id="hero", action="move")["sprite"],
            "hero_walk_1")
        self.assertEqual(tool.sample(
            "hero_move", 205, actor_id="hero", action="move")["sprite"],
            "hero_walk_0")
        s.undo()
        self.assertEqual(tool.animations(), ())
        s.redo()
        self.assertEqual(tool.animations(), ("hero_move_anim",))

    def test_invalid_paths_frames_slot_and_stale_plan_fail_closed(self):
        s = editor()
        tool = AnimationHitboxStudio(s)
        baseline = s.snapshot().to_dict()
        for sprite, path in (
            ("broken", "../escape.png"),
            ("bad", "/tmp/unsafe.png"),
            ("other", "assets/wrong.jpg"),
        ):
            with self.subTest(path=path), self.assertRaises(AuthoringError):
                tool.preview_sprite(sprite, path)
        with self.assertRaises(AuthoringError):
            tool.preview_animation("anim", [{"sprite": "missing", "duration_ms": 1}])
        with self.assertRaises(AuthoringError):
            tool.preview_animation("anim", [{"sprite": "bad", "duration_ms": 0}])
        with self.assertRaises(R28DError):
            tool.preview_animation("anim", [], expected_revision=999)
        self.assertEqual(s.snapshot().to_dict(), baseline)
        pending = tool.preview_sprite("hero", "art/hero.png")
        tool.apply(pending)
        with self.assertRaises(AuthoringError):
            tool.apply(pending)
        with self.assertRaises(AuthoringError):
            tool.preview_sprite("hero", "art/again.png")
        with self.assertRaises(R28DError):
            tool.hitboxes("unknown")
        self.assertEqual(
            AssetRegistry(tool.manifest()).require_reference("hero", "sprite")["path"],
            "art/hero.png")

    def test_asset_roundtrip_is_canonical_project_not_sidecar(self):
        s = editor()
        editor_tool = AnimationHitboxStudio(s)
        editor_tool.apply(editor_tool.preview_sprite("hero_idle", "art/hero_idle.png"))
        editor_tool.apply(editor_tool.preview_animation(
            "hero_idle_a", [{"sprite": "hero_idle", "duration_ms": 100}],
            slot="hero_idle"))
        with TemporaryDirectory() as folder:
            path = Path(folder) / "jeanne.json"
            s.save_as(path)
            reopened = AuthoringSession.open(path)
            self.assertEqual(AnimationHitboxStudio(reopened).manifest(),
                             editor_tool.manifest())
            self.assertEqual(reopened.snapshot().to_dict()["content"]["version"], 1)


class QuestPlaytestTests(unittest.TestCase):
    def test_event_graph_r9_is_canonical_and_does_not_mutate_on_inspect(self):
        s = editor()
        events = EventStudio(s)
        events.create(
            MISSION, "r28_first", condition("tick", tick=2),
            [action("message", text="Premier évènement")])
        events.create(
            MISSION, "r28_second", condition("tick", tick=5),
            [action("message", text="Second évènement")])
        graph = EventQuestGraph(s)
        before = s.snapshot().to_dict()
        view = graph.inspect(MISSION)
        self.assertEqual(view["mode"]["combat"], "TACTICAL_CT")
        self.assertIn("arrival", {scene["id"] for scene in view["story_scenes"]})
        self.assertEqual(s.snapshot().to_dict(), before)
        graph.link(MISSION, "r28_second", "r28_first",
                   expected_revision=s.revision)
        linked = events.event(MISSION, "r28_second")
        self.assertIn("r28_first", linked.get("after", []))
        with self.assertRaises((AuthoringError, RuleError)):
            graph.link(MISSION, "r28_first", "r28_second")
        s.undo()
        self.assertNotIn("r28_first",
                         events.event(MISSION, "r28_second").get("after", []))

    def test_playtest_roundtrip_is_validated_isolated_and_restorable(self):
        s = editor()
        original = s.snapshot().to_dict()
        playtest = IsolatedPlaytest(s)
        report = playtest.run("main", seed=13, expected_revision=0)
        self.assertTrue(report["checkpoint_verified"])
        self.assertTrue(report["author_dirty_unchanged"])
        self.assertEqual(report["initial_scene"], "arrival")
        self.assertEqual(len(report["checkpoint_digest"]), 64)
        self.assertEqual(s.snapshot().to_dict(), original)
        battle = playtest.run(
            "main", choice_id="enter", mission_id=MISSION, seed=13)
        self.assertTrue(battle["checkpoint_verified"])
        self.assertEqual(battle["mission"], MISSION)
        self.assertEqual(battle["mode"], "battle")
        self.assertEqual(s.snapshot().to_dict(), original)

    def test_playtest_rejects_invalid_choice_seed_and_stale_revision(self):
        s = editor()
        engine = IsolatedPlaytest(s)
        before = s.snapshot().to_dict()
        with self.assertRaises(R28DError):
            engine.run("main", seed=-1)
        with self.assertRaises(R28DError):
            engine.run("main", expected_revision=1)
        with self.assertRaises(RuleError):
            engine.run("main", choice_id="not_a_choice")
        with self.assertRaises(RuleError):
            engine.run("main", mission_id="not_a_mission")
        self.assertEqual(s.snapshot().to_dict(), before)

    def test_profile_manifest_preserved_across_isolated_roundtrip(self):
        from drawtemp.studio.profile_authoring import (
            preview_profile_edit, apply_profile_edit,
        )
        s = editor()
        apply_profile_edit(s, preview_profile_edit(
            s, "arrival", {"preset": "narrative"}))
        before = deepcopy(s.snapshot().to_dict())
        result = IsolatedPlaytest(s).run("main", choice_id="enter", seed=2)
        self.assertTrue(result["checkpoint_verified"])
        self.assertEqual(s.snapshot().to_dict(), before)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "Qt runtime unavailable")
class R28DQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_workbench_all_tabs_share_session_and_no_implicit_write(self):
        from drawtemp.studio.r28d_workflow_qt import R28DWorkspace
        s = editor()
        before = s.snapshot().to_dict()
        view = R28DWorkspace(s)
        self.assertEqual(view.tabs.count(), 3)
        self.assertIs(view.animation.editor.session, s)
        self.assertIs(view.events.editor.session, s)
        self.assertIs(view.playtest.editor.session, s)
        self.assertEqual(s.snapshot().to_dict(), before)
        view.animation.sprite_id.setText("qt_hero")
        view.animation.sprite_path.setText("art/qt_hero.png")
        view.animation.preview_sprite()
        self.assertTrue(view.animation.apply_button.isEnabled(),
                        view.animation.preview.toPlainText())
        self.assertEqual(s.revision, 0)
        view.animation.apply_changes()
        self.assertEqual(s.revision, 1)
        view.refresh()
        view.playtest.run_test()
        self.assertIn("checkpoint_verified", view.playtest.report.toPlainText())
        view.close()

    def test_shell_events_page_hosts_real_roundtrip_workbench(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        with TemporaryDirectory() as folder:
            s = editor()
            settings = QSettings(str(Path(folder) / "r28.ini"), QSettings.IniFormat)
            shell = StudioWindow(s, settings=settings)
            shell.navigate("events")
            page = shell._models["events"]
            self.assertIs(page.session, s)
            self.assertEqual(shell.workspace_tabs.currentWidget(), page)
            self.assertEqual(page.tabs.count(), 3)
            shell.close()


if __name__ == "__main__":
    unittest.main()
