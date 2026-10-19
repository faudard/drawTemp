"""R28.C acceptance: canonical skill/enemy editors, mode gates and Qt wiring."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.genre_rules_designer import (
    DesignPreview, GenreDesignError, GenreRulesDesigner,
)
from drawtemp.studio.profile_authoring import (
    apply_profile_edit, preview_profile_edit,
)
from sporebound.model import Content


def new_designer():
    session = AuthoringSession.new(*reference_project())
    return session, GenreRulesDesigner(session)


class GameplayDesignerTests(unittest.TestCase):
    def test_ability_preview_is_pure_then_one_undo_for_skill_and_effect(self):
        session, editor = new_designer()
        skill_id = editor.skills()[0].id
        original = editor.skill(skill_id)
        content = session.snapshot().to_dict()["content"]
        new_cost = original["cost"] + 1 if original["cost"] < 100 else 99
        new_power = original["effects"][0]["power"] + 1
        if new_power > 10000:
            new_power = 9999
        revision = session.revision
        result = editor.preview_skill(
            MISSION, skill_id, {"cost": new_cost},
            effect_index=0, effect={"power": new_power},
            expected_revision=revision)
        self.assertEqual(result.kind, "skill")
        self.assertTrue(result.report["changed"])
        self.assertEqual(session.revision, revision)
        self.assertEqual(session.snapshot().to_dict()["content"], content)
        editor.apply(result)
        self.assertEqual(session.revision, revision + 1)
        self.assertEqual(editor.skill(skill_id)["cost"], new_cost)
        self.assertEqual(editor.skill(skill_id)["effects"][0]["power"], new_power)
        self.assertEqual(session.snapshot().to_dict()["content"]["version"], 1)
        session.undo()
        self.assertEqual(editor.skill(skill_id), original)
        session.redo()
        self.assertEqual(editor.skill(skill_id)["cost"], new_cost)

    def test_skill_changes_use_existing_Content_and_validators(self):
        session, editor = new_designer()
        skill_id = editor.skills()[0].id
        baseline = session.snapshot().to_dict()
        original = editor.skill(skill_id)
        with self.assertRaises(AuthoringError):
            editor.preview_skill(
                MISSION, skill_id,
                {"min_range": original["range"] + 1},
                expected_revision=session.revision)
        with self.assertRaises(GenreDesignError):
            editor.preview_skill(MISSION, skill_id, {"new_runtime_field": 4})
        with self.assertRaises(GenreDesignError):
            editor.preview_skill(MISSION, skill_id, {})
        with self.assertRaises(GenreDesignError):
            editor.preview_skill(MISSION, skill_id, {},
                                 effect_index=999, effect={"power": 3})
        with self.assertRaises(AuthoringError):
            editor.preview_skill(
                MISSION, skill_id, {"target": "not-a-target"})
        self.assertEqual(session.snapshot().to_dict(), baseline)
        # A skill still validates with the existing tactical Content model.
        Content.from_dict(session.snapshot().to_dict()["content"])

    def test_action_and_rpg_profiles_do_not_fake_runtime_bindings(self):
        session, editor = new_designer()
        arrival = "arrival"
        apply_profile_edit(session, preview_profile_edit(
            session, arrival, {"preset": "action"}))
        note = editor.compatibility(arrival)
        self.assertEqual(note["combat"], "ACTION_REALTIME")
        self.assertFalse(note["editable_in_this_workbench"])
        self.assertIsNone(note["engine"])
        self.assertEqual(editor.compatibility(MISSION)["combat"], "TACTICAL_CT")
        with self.assertRaises(GenreDesignError):
            editor.preview_skill(arrival, editor.skills()[0].id, {"cost": 2})
        self.assertEqual(editor.compatibility(MISSION)["engine"],
                         "sporebound.engine.Battle")

    def test_enemy_preview_uses_real_battle_and_edit_is_atomic(self):
        session, editor = new_designer()
        enemy_id = editor.enemies(MISSION)[0][0]
        before = editor.enemy(MISSION, enemy_id)
        document = session.snapshot().to_dict()
        preview = editor.preview_enemy(
            MISSION, enemy_id, roles=("leader",), squad="r28_gate",
            expected_revision=session.revision, seed=41)
        self.assertEqual(preview.kind, "enemy")
        self.assertTrue(preview.report["changed"])
        self.assertIn("leader", preview.report["after"]["tags"])
        self.assertEqual(
            preview.report["observed_initial_state"]["behavior"], "tactical")
        self.assertEqual(len(
            preview.report["observed_initial_state"]["battle_digest"]), 64)
        self.assertEqual(session.snapshot().to_dict(), document)
        repeat = editor.preview_enemy(
            MISSION, enemy_id, roles=("leader",), squad="r28_gate", seed=41)
        self.assertEqual(
            preview.report["observed_initial_state"]["battle_digest"],
            repeat.report["observed_initial_state"]["battle_digest"])
        editor.apply(preview)
        self.assertIn("squad:r28_gate", editor.enemy(MISSION, enemy_id)["tags"])
        session.undo()
        self.assertEqual(editor.enemy(MISSION, enemy_id), before)
        session.redo()
        self.assertIn("leader", editor.enemy(MISSION, enemy_id)["tags"])

    def test_invalid_ai_and_foreign_or_stale_plans_fail_closed(self):
        session, editor = new_designer()
        enemy_id = editor.enemies(MISSION)[0][0]
        baseline = session.snapshot().to_dict()
        with self.assertRaises(AuthoringError):
            editor.preview_enemy(MISSION, enemy_id, doctrine="does_not_exist")
        with self.assertRaises(AuthoringError):
            editor.preview_enemy(MISSION, enemy_id, roles=("leader", "leader"))
        with self.assertRaises(GenreDesignError):
            editor.preview_enemy(MISSION, "nobody")
        with self.assertRaises(GenreDesignError):
            editor.preview_enemy(MISSION, enemy_id, seed=-1)
        self.assertEqual(session.snapshot().to_dict(), baseline)
        valid = editor.preview_enemy(MISSION, enemy_id, roles=("leader",))
        other_session, other = new_designer()
        with self.assertRaises(AuthoringError):
            other.apply(valid)
        editor.apply(valid)
        with self.assertRaises(AuthoringError):
            editor.apply(valid)
        with self.assertRaises(GenreDesignError):
            editor.preview_enemy(MISSION, enemy_id, expected_revision=0)
        self.assertEqual(other_session.revision, 0)

    def test_save_reopen_preserves_abilities_and_enemy_ids(self):
        session, editor = new_designer()
        sid = editor.skills()[0].id
        eid = editor.enemies(MISSION)[0][0]
        old = editor.skill(sid)
        new_cost = old["cost"] + 1 if old["cost"] < 100 else 99
        editor.apply(editor.preview_skill(MISSION, sid, {"cost": new_cost}))
        editor.apply(editor.preview_enemy(MISSION, eid, roles=("leader",)))
        with TemporaryDirectory() as folder:
            path = Path(folder) / "r28.json"
            session.save_as(path)
            reopened = GenreRulesDesigner(AuthoringSession.open(path))
            self.assertEqual(reopened.skill(sid)["cost"], new_cost)
            self.assertIn("leader", reopened.enemy(MISSION, eid)["tags"])
            self.assertEqual(reopened.session.snapshot().to_dict()["project"],
                             session.snapshot().to_dict()["project"])


@unittest.skipUnless(importlib.util.find_spec("PySide6"), "PySide6 unavailable")
class GameplayQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_ability_and_enemy_controls_commit_to_same_session(self):
        from drawtemp.studio.genre_rules_qt import GenreRulesWorkspace
        session, editor = new_designer()
        widget = GenreRulesWorkspace(session)
        self.assertIs(widget.abilities.designer.session, session)
        self.assertIs(widget.enemies.designer.session, session)
        self.assertGreater(widget.abilities.skill_id.count(), 0)
        self.assertGreater(widget.enemies.actor.count(), 0)
        ability = widget.abilities
        old = ability.cost.value()
        ability.cost.setValue(old + 1 if old < 100 else old - 1)
        ability.preview_changes()
        self.assertTrue(ability.apply_button.isEnabled(),
                        ability.report.toPlainText())
        ability.apply_changes()
        self.assertEqual(session.revision, 1)
        enemy = widget.enemies
        enemy.squad.setText("r28qt")
        enemy.preview_changes()
        self.assertTrue(enemy.apply_button.isEnabled(),
                        enemy.report.toPlainText())
        enemy.apply_changes()
        self.assertEqual(session.revision, 2)
        widget.refresh()
        session.undo()
        widget.refresh()
        self.assertNotIn(
            "squad:r28qt", editor.enemy(MISSION, editor.enemies(MISSION)[0][0])["tags"])
        widget.close()

    def test_shell_navigation_and_shared_session(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        session, _ = new_designer()
        with TemporaryDirectory() as folder:
            settings = QSettings(str(Path(folder) / "settings.ini"), QSettings.IniFormat)
            window = StudioWindow(session, settings=settings)
            self.assertIn("go_gameplay", window.commands)
            window.navigate("gameplay")
            pane = window._models["gameplay"]
            self.assertIs(pane.session, session)
            self.assertIs(window.workspace_tabs.currentWidget(), pane)
            window.close()


if __name__ == "__main__":
    unittest.main()
