"""R41.B1: real AuthoringSession and Player roster headless regression tests."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.player.controller import PlayerController
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.studio.party_authoring import (
    apply_party_edit, inspect_party, party_campaigns, party_heroes,
    preview_party_edit,
)
from sporebound.classic_party import EXTENSION
from sporebound.model import RuleError
from tests_standalone.test_r41_classic_party import party_fixture


class R41PartyStudioTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = party_fixture()
        self.editor = AuthoringSession.new(self.content, self.project)

    def test_preview_apply_undo_redo_is_one_project_transaction(self):
        initial = self.editor.snapshot().to_dict()
        self.assertIn(("main", "Campagne principale"),
                      party_campaigns(self.editor.snapshot()))
        self.assertIn(("jeanne", "Jeanne"), party_heroes(self.editor.snapshot()))
        draft = preview_party_edit(
            self.editor, "main", recruitable=["jeanne", "margot"],
            initial=["jeanne", "margot"], active=["jeanne", "margot"],
            max_active=2, expected_revision=initial["revision"])
        self.assertEqual(self.editor.snapshot().to_dict(), initial)
        transition = apply_party_edit(self.editor, draft)
        selected = inspect_party(transition.snapshot, "main")["selection"]
        self.assertEqual(selected["initial"], ["jeanne", "margot"])
        self.assertEqual(selected["active"], ["jeanne", "margot"])
        self.assertTrue(self.editor.snapshot().can_undo)
        self.editor.undo()
        self.assertEqual(self.editor.snapshot().to_dict()["project"],
                         initial["project"])
        self.editor.redo()
        self.assertEqual(inspect_party(self.editor.snapshot(), "main")[
            "selection"]["initial"], ["jeanne", "margot"])
        # No R41 sidecar; both documents remain canonical and valid.
        self.assertEqual(self.editor.snapshot().to_dict()["content"],
                         initial["content"])

    def test_create_opt_in_party_without_touching_legacy_other_extensions(self):
        project = deepcopy(self.project)
        project.extensions.pop(EXTENSION)
        project.extensions["org.example.marker"] = {
            "schema_version": 1, "data": {"sample": 1}}
        editor = AuthoringSession.new(self.content, project)
        self.assertFalse(inspect_party(editor.snapshot(), "main")["enabled"])
        draft = preview_party_edit(
            editor, "main", recruitable=["jeanne", "margot"],
            initial=["jeanne"], active=["jeanne"], max_active=2)
        apply_party_edit(editor, draft)
        data = editor.snapshot().to_dict()["project"]
        self.assertEqual(data["extensions"]["org.example.marker"]["data"], {"sample": 1})
        self.assertIn(EXTENSION, data["extensions"])

    def test_stale_foreign_and_invalid_changes_cannot_mutate(self):
        snapshot = self.editor.snapshot().to_dict()
        for params in (
            {"recruitable": ["jeanne"], "initial": ["margot"],
             "active": ["margot"], "max_active": 2},
            {"recruitable": ["jeanne", "margot"], "initial": ["jeanne"],
             "active": ["jeanne", "margot"], "max_active": 2},
            {"recruitable": ["jeanne", "jeanne"], "initial": ["jeanne"],
             "active": ["jeanne"], "max_active": 2},
            {"recruitable": ["jeanne"], "initial": ["jeanne"],
             "active": ["jeanne"], "max_active": True},
        ):
            with self.subTest(params=params), self.assertRaises(RuleError):
                preview_party_edit(self.editor, "main", **params)
            self.assertEqual(self.editor.snapshot().to_dict(), snapshot)
        good = dict(recruitable=["jeanne", "margot"],
                    initial=["jeanne"], active=["jeanne"], max_active=1)
        with self.assertRaises(RuleError):
            preview_party_edit(self.editor, "missing", **good)
        stale = preview_party_edit(self.editor, "main", **good)
        applied = preview_party_edit(
            self.editor, "main", recruitable=["jeanne", "margot"],
            initial=["jeanne"], active=["jeanne"], max_active=2)
        apply_party_edit(self.editor, applied)
        with self.assertRaises(RuleError):
            apply_party_edit(self.editor, stale)
        with self.assertRaises(RuleError):
            preview_party_edit(self.editor, "main",
                               expected_revision=snapshot["revision"], **good)

    def test_no_rpg_profile_refuses_creating_party(self):
        project = deepcopy(self.project)
        project.game_modes = {}
        project.extensions.pop(EXTENSION)
        editor = AuthoringSession.new(self.content, project)
        before = editor.snapshot().to_dict()
        with self.assertRaises(RuleError):
            preview_party_edit(editor, "main", recruitable=["jeanne"],
                               initial=["jeanne"], active=["jeanne"],
                               max_active=1)
        self.assertEqual(editor.snapshot().to_dict(), before)

    def test_player_state_switch_and_autosave_roundtrip(self):
        with TemporaryDirectory() as path:
            controller = PlayerController(self.content, self.project,
                                          "main", Path(path), seed=23)
            state = controller.new_game()
            self.assertEqual(state["party"]["capacity"], 2)
            self.assertEqual([r["id"] for r in state["party"]["heroes"]],
                             ["jeanne"])
            with self.assertRaises(ValueError):
                controller.toggle_party_member("jeanne")
            rev = controller.session.snapshot().revision
            controller.session.party_recruit("margot", expected_revision=rev)
            party = controller.state()["party"]
            self.assertEqual(len(party["heroes"]), 2)
            self.assertEqual(party["active"], ["jeanne"])
            controller.toggle_party_member("margot")
            self.assertEqual(controller.state()["party"]["active"],
                             ["jeanne", "margot"])
            with self.assertRaises(ValueError):
                controller.toggle_party_member("missing")
            # Cannot exceed capacity; removal preserves the recruited reserve.
            controller.toggle_party_member("jeanne")
            self.assertEqual(controller.state()["party"]["active"], ["margot"])
            controller.save(1)
            another = PlayerController(self.content, self.project,
                                       "main", Path(path), seed=23)
            another.load(1)
            self.assertEqual(another.state()["party"]["active"], ["margot"])
            self.assertEqual(len(another.state()["party"]["heroes"]), 2)


if __name__ == "__main__":
    unittest.main()
