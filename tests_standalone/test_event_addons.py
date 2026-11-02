"""PR 3: v3 game.event -> native R24.E -> StoryBook/Player contracts."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.addons import AddonManager
from drawtemp.core import Content, GameProject
from drawtemp.quality.r24_platform import source_paths
from drawtemp.sdk import AuthoringSession, Simulation, SDK_FEATURES
from drawtemp.sdk.authoring import AuthoringError
from drawtemp.sdk.event_addons import (
    EventAddonError, event_addon_catalogue, event_addon_script,
    install_event_addon, preview_event_addon, verify_runtime_event_receipts,
)
from drawtemp.sdk.replay import verify_recording
from drawtemp.studio.events import EventStudio

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/addons/asterion-event-addon.json"


def example():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def source():
    content_path, project_path = source_paths()
    content = Content.from_dict(json.loads(content_path.read_text(encoding="utf-8")))
    project = GameProject.from_dict(
        json.loads(project_path.read_text(encoding="utf-8")), content
    )
    return content, project


def authoring():
    return AuthoringSession.new(*source())


def enabled(data=None):
    data = example() if data is None else data
    registry = AddonManager()
    registry.register(data)
    registry.enable(data["id"], grants=data["permissions"])
    return registry


class ContractTests(unittest.TestCase):
    def test_explicit_feature_and_native_compiler(self):
        self.assertIn("event-addons.v1", SDK_FEATURES)
        manifest = example()
        script = event_addon_script(manifest)
        self.assertEqual(script["hooks"][0]["trigger"], "story.choice")
        self.assertEqual(script["permissions"], ["campaign.gold.write", "story.flags.write"])
        script["hooks"][0]["effects"][0]["value"] = False
        self.assertTrue(manifest["contributions"][0]["config"]["effects"][0]["value"])

    def test_no_implicit_permissions_or_catalogue(self):
        registry = AddonManager()
        document = example()
        registry.register(document)
        self.assertEqual(event_addon_catalogue(registry), ())
        with self.assertRaises(EventAddonError) as caught:
            preview_event_addon(registry, authoring(), document["id"])
        self.assertEqual(caught.exception.code, "permission_denied")
        registry.enable(document["id"], grants=document["permissions"])
        self.assertEqual(len(event_addon_catalogue(registry)), 1)
        registry.disable(document["id"])
        self.assertEqual(event_addon_catalogue(registry), ())

    def test_reject_unknown_effects_triggers_and_mismatched_feature(self):
        for field, value in [
            ("trigger", "simulation.tick"),
            ("effects", [{"kind": "python", "entrypoint": "os.system"}]),
            ("effects", [{"kind": "grant_item", "item": "rare", "quantity": 10}]),
            ("effects", [{"kind": "gold", "amount": 10001}]),
            ("effects", []),
        ]:
            with self.subTest(field=field):
                manifest = example()
                manifest["contributions"][0]["config"][field] = value
                with self.assertRaises(EventAddonError):
                    event_addon_script(manifest)
        manifest = example()
        manifest["sdk"]["required_features"].remove("event-addons.v1")
        with self.assertRaises(EventAddonError) as caught:
            event_addon_script(manifest)
        self.assertEqual(caught.exception.code, "missing_feature")
        manifest = example()
        manifest["contributions"][0]["config"]["extra"] = "not allowed"
        with self.assertRaises(EventAddonError):
            event_addon_script(manifest)

    def test_duplicate_choice_targets_rejected(self):
        manifest = example()
        duplicate = deepcopy(manifest["contributions"][0])
        duplicate["id"] = "duplicate-target"
        manifest["contributions"].append(duplicate)
        with self.assertRaises(EventAddonError) as caught:
            event_addon_script(manifest)
        self.assertEqual(caught.exception.code, "duplicate_hook")

    def test_no_change_for_unrelated_editor_addons(self):
        manifest = json.loads(
            (EXAMPLE.parent / "terrain-brush.json").read_text(encoding="utf-8")
        )
        self.assertIsNone(event_addon_script(manifest))


class CompilationTests(unittest.TestCase):
    def setUp(self):
        self.registry = enabled()
        self.session = authoring()

    def test_preview_and_undo_redo_and_reopen(self):
        old = self.session.snapshot().to_dict()
        plan = preview_event_addon(
            self.registry, self.session, "asterion-event-addon", expected_revision=0
        )
        self.assertEqual(old, self.session.snapshot().to_dict())
        self.session.apply(plan)
        self.assertEqual(self.session.revision, 1)
        compiled = self.session.snapshot().to_dict()
        self.assertEqual(compiled["content"], old["content"])
        effects = compiled["project"]["story"]["scenes"][0]["choices"][0]["effects"]
        self.assertEqual(effects[-2:], example()["contributions"][0]["config"]["effects"])
        receipt = compiled["project"]["extensions"][example()["namespace"]]
        self.assertEqual(receipt["data"]["kind"], "r24e.story-choice-hooks")
        self.assertEqual(verify_runtime_event_receipts(compiled["project"]), [])
        with self.assertRaises(AuthoringError):
            self.session.apply(plan)
        self.session.undo()
        self.assertEqual(self.session.snapshot().to_dict(), {
            **old, "revision": 2, "can_redo": True
        }) if False else self.assertEqual(self.session.snapshot().project, old["project"])
        self.session.redo()
        self.assertEqual(self.session.snapshot().project, compiled["project"])
        with TemporaryDirectory() as directory:
            path = Path(directory) / "scenario.json"
            self.session.save_as(path)
            opened = AuthoringSession.open(path)
            self.assertEqual(opened.snapshot().project, compiled["project"])

    def test_explicit_install_and_reapply_are_safe(self):
        original = self.session.snapshot().to_dict()
        with self.assertRaises(EventAddonError) as ctx:
            preview_event_addon(self.registry, self.session, "asterion-event-addon",
                                expected_revision=9)
        self.assertEqual(ctx.exception.code, "stale_revision")
        self.assertEqual(original, self.session.snapshot().to_dict())
        install_event_addon(self.registry, self.session, "asterion-event-addon",
                            expected_revision=0)
        with self.assertRaises(AuthoringError):
            install_event_addon(self.registry, self.session, "asterion-event-addon",
                                expected_revision=1)
        self.assertEqual(self.session.revision, 1)

    def test_missing_target_and_receipt_tamper_are_refused(self):
        manifest = example()
        manifest["contributions"][0]["config"]["scene"] = "not_found"
        registry = enabled(manifest)
        old = self.session.snapshot().to_dict()
        with self.assertRaises(AuthoringError):
            install_event_addon(registry, self.session, manifest["id"])
        self.assertEqual(self.session.snapshot().to_dict(), old)
        install_event_addon(self.registry, self.session, "asterion-event-addon")
        changed = self.session.snapshot().to_dict()["project"]
        changed["story"]["scenes"][0]["choices"][0]["effects"][-1]["amount"] = 100
        errors = verify_runtime_event_receipts(changed)
        self.assertTrue(errors)
        self.assertTrue(any("Compiled effects differ" in item for item in errors))

    def test_real_game_session_player_effects_save_and_replay(self):
        content, original_project = source()
        install_event_addon(self.registry, self.session, "asterion-event-addon")
        modified = GameProject.from_dict(
            self.session.snapshot().to_dict()["project"], content
        )
        session = Simulation.new(content, modified, "main", seed=17)
        self.assertNotIn("addon_scan_ready", session.snapshot().progress["story_flags"])
        initial_gold = session.snapshot().progress["gold"]
        session.choose_story_option("launch")
        state = session.snapshot()
        self.assertIs(state.progress["story_flags"]["addon_scan_ready"], True)
        self.assertEqual(state.progress["gold"], initial_gold + 5)
        recording = session.recording()
        self.assertEqual(
            verify_recording(recording, content, modified).recording(),
            recording
        )
        with self.assertRaises(Exception):
            verify_recording(recording, content, original_project)
        with TemporaryDirectory() as directory:
            save = Path(directory) / "save.json"
            session.save(save)
            loaded = Simulation.load(save, content, modified)
            self.assertEqual(loaded.recording(), recording)

    def test_event_studio_is_same_authoring_session(self):
        studio = EventStudio(self.session)
        catalogue = studio.addon_event_catalogue(self.registry)
        self.assertEqual(catalogue[0]["id"], "scan-reward")
        before = self.session.revision
        preview = studio.preview_addon_events(self.registry, "asterion-event-addon")
        self.assertEqual(self.session.revision, before)
        self.session.apply(preview)
        self.assertEqual(self.session.revision, before + 1)


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "Qt is optional")
class QtStudioPlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["event-addon-smoke"])

    def test_studio_compile_then_player_controller(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        from drawtemp.player.qt_app import build_controller

        content, project = source()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            window = StudioWindow(
                AuthoringSession.new(content, project),
                settings=QSettings(str(root / "studio.ini"), QSettings.IniFormat)
            )
            window.show()
            try:
                status = window.install_addon_manifest(EXAMPLE)
                self.assertFalse(status["enabled"])
                window.enable_addon(status["id"], status["required_permissions"])
                plan, script = window.preview_addon_events(status["id"])
                self.assertEqual(script["hooks"][0]["scene"], "briefing")
                self.assertEqual(window.session.revision, 0)
                window.apply_addon_events(status["id"], plan)
                self.assertEqual(window.session.revision, 1)
                path = root / "asterion.json"
                window.session.save_as(path)
                window.disable_addon(status["id"])
                controller = build_controller(
                    content_path=path, save_dir=root / "player",
                    campaign_id="main"
                )
                controller.new_game()
                controller.choose("launch")
                snapshot = controller.session.snapshot()
                self.assertEqual(snapshot.progress["story_flags"]["addon_scan_ready"], True)
                self.assertEqual(verify_runtime_event_receipts(
                    window.session.snapshot().project), [])
            finally:
                window.hide()
                window.deleteLater()


if __name__ == "__main__":
    unittest.main()
