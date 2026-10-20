"""R75.A reviewed narrative and three-ending persistence regression tests."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.studio.r75_narrative_assist import (
    NarrativeAssistController, NarrativeAssistError, three_endings_template)
from sporebound.campaign import Campaign
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.narrative import StoryBook
from sporebound.studio_transaction import validate_pair
from sporebound.tactical_rpg3 import authored_rules_for_document


class R75NarrativeTests(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.session = AuthoringSession.new(content, project)
        self.controller = NarrativeAssistController(self.session)
        self.proposal = three_endings_template(MISSION)
        self.before = self.session.snapshot().to_dict()

    def test_no_implicit_mutation_human_review_undo_redo(self):
        review = self.controller.preview(self.proposal)
        self.assertEqual(self.session.snapshot().to_dict(), self.before)
        self.assertEqual(len(review.ending_paths), 3)
        self.assertEqual(len(review.added_scenes), 5)
        self.assertEqual(len(review.proposal_sha256), 64)
        self.assertTrue(review.to_dict()["approval_required"])
        self.assertFalse(review.to_dict()["gameplay_certified"])
        with self.assertRaises(NarrativeAssistError) as denied:
            self.controller.apply(review)
        self.assertEqual(denied.exception.code, "approval_required")
        self.assertEqual(self.before, self.session.snapshot().to_dict())
        after = self.controller.apply(review, approved=True).snapshot.to_dict()
        self.assertEqual(after["content"], self.before["content"])
        self.assertEqual(after["project"]["story"]["entry_scenes"],
                         self.before["project"]["story"]["entry_scenes"])
        self.assertEqual(len(after["project"]["story"]["scenes"]),
                         len(self.before["project"]["story"]["scenes"]) + 5)
        validate_pair(after["content"], after["project"])
        self.assertEqual(self.session.undo().snapshot.to_dict()["project"],
                         self.before["project"])
        self.assertEqual(self.session.redo().snapshot.to_dict()["project"],
                         after["project"])
        with self.assertRaises(NarrativeAssistError):
            self.controller.apply(review, approved=True)

    def test_three_real_paths_and_campaign_slot_roundtrip(self):
        review = self.controller.preview(self.proposal)
        self.controller.apply(review, approved=True)
        result = self.session.snapshot().to_dict()
        content = Content.from_dict(
            result["content"], rules=authored_rules_for_document(result["content"]))
        project = GameProject.from_dict(result["project"], content)
        book = StoryBook(project.story, content, project.campaigns)
        for start, decision, ending, value in (
            ("help", "save", "r75_rescue", "rescue"),
            ("talk", "peace", "r75_pact", "pact"),
            ("leave", "fallback", "r75_depart", "depart"),
        ):
            with self.subTest(start=start):
                progress = Campaign(unlocked=[MISSION])
                progress.story_started = True
                progress.story_digest = book.digest
                progress.story_pending = self.proposal["entry_scene"]
                progress = book.choose(progress, start)
                with TemporaryDirectory() as directory:
                    path = Path(directory) / "campaign.json"
                    progress.save(path)
                    progress = Campaign.load(path)
                self.assertIn(decision, [c["id"] for c in book.choices(progress)])
                progress = book.choose(progress, decision)
                self.assertEqual(progress.story_pending, ending)
                progress = book.choose(progress, "end")
                self.assertEqual(progress.story_flags["r75_outcome"], value)
                self.assertEqual(progress.story_pending, "")
                self.assertEqual(len(progress.story_history), 3)

    def test_bad_edges_cycles_unreachable_branches_are_rejected(self):
        bad = deepcopy(self.proposal)
        bad["scenes"][0]["choices"][0]["next_scene"] = "outside"
        with self.assertRaises(NarrativeAssistError) as err:
            self.controller.preview(bad)
        self.assertEqual(err.exception.code, "external_link")
        bad = deepcopy(self.proposal)
        bad["scenes"][1]["choices"][0]["next_scene"] = "r75_offer"
        with self.assertRaises(AuthoringError):
            self.controller.preview(bad)
        bad = deepcopy(self.proposal)
        bad["scenes"][0]["choices"] = bad["scenes"][0]["choices"][:1]
        with self.assertRaises(NarrativeAssistError) as err:
            self.controller.preview(bad)
        self.assertEqual(err.exception.code, "unreachable_scene")
        bad = deepcopy(self.proposal)
        bad["endings"].pop()
        with self.assertRaises(NarrativeAssistError) as err:
            self.controller.preview(bad)
        self.assertEqual(err.exception.code, "unreachable_ending")
        bad = deepcopy(self.proposal)
        bad["scenes"][0]["choices"].append({
            "id": "dead", "label": "Impossible",
            "when": {"flag": "unused", "eq": True},
            "next_scene": "r75_decision", "effects": []})
        with self.assertRaises(NarrativeAssistError) as err:
            self.controller.preview(bad)
        self.assertEqual(err.exception.code, "unreachable_choice")
        self.assertEqual(self.before, self.session.snapshot().to_dict())

    def test_provenance_permissions_schema_script_injection_and_conflict(self):
        cases = (
            (lambda p: p["source"].update(redistribution_allowed=False), "invalid_rights"),
            (lambda p: p["source"].update(license=""), "invalid_rights"),
            (lambda p: p["scenes"][0]["choices"][0].update(
                effects=[{"kind": "python", "code": "pass"}]), "unsafe_effect"),
            (lambda p: p.update(version=True), "invalid_version"),
            (lambda p: p.update(unexpected={}), "invalid_proposal"),
        )
        for change, code in cases:
            bad = deepcopy(self.proposal)
            change(bad)
            with self.subTest(code=code), self.assertRaises(NarrativeAssistError) as err:
                self.controller.preview(bad)
            self.assertEqual(err.exception.code, code)
        bad = deepcopy(self.proposal)
        bad["hook"] = {"kind": "entry_scenes", "id": "main"}
        with self.assertRaises(NarrativeAssistError) as err:
            self.controller.preview(bad)
        self.assertEqual(err.exception.code, "hook_conflict")
        self.assertEqual(self.before, self.session.snapshot().to_dict())

    def test_forged_review_and_edit_undo_aba_are_rejected(self):
        review = self.controller.preview(self.proposal)
        with self.assertRaises(NarrativeAssistError):
            self.controller.apply(deepcopy(review), approved=True)
        self.session.apply(self.session.preview_project(
            lambda p: {**p, "subtitle": "Changed"}))
        self.session.undo()
        with self.assertRaises(AuthoringError) as err:
            self.controller.apply(review, approved=True)
        self.assertEqual(err.exception.code, "stale_revision")

    def test_save_is_explicit_and_reopen_canonical_project(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "r75.json"
            AuthoringSession.new(
                self.before["content"], self.before["project"]).save_as(path)
            game = path.with_name("r75.game.json")
            previous = (path.read_bytes(), game.read_bytes())
            session = AuthoringSession.open(path)
            controller = NarrativeAssistController(session)
            review = controller.preview(self.proposal)
            controller.apply(review, approved=True)
            self.assertEqual((path.read_bytes(), game.read_bytes()), previous)
            session.save()
            self.assertNotEqual(game.read_bytes(), previous[1])
            self.assertEqual(AuthoringSession.open(path).snapshot().to_dict()["project"],
                             session.snapshot().to_dict()["project"])


if __name__ == "__main__":
    unittest.main()
