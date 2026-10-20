"""R48.A: two-author deterministic collaboration and fail-closed merge tests."""
from copy import deepcopy
from dataclasses import replace
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.collaboration import (
    CollaborationController, CollaborationError, make_revision,
)
from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.semantic_review import preview_merge


class CollaborationTests(unittest.TestCase):
    def setUp(self):
        content, project = reference_project()
        self.content = content.to_dict()
        self.project = project.to_dict()
        self.base = make_revision(self.content, self.project, author="base")
        self.session = AuthoringSession.new(content, project)
        self.controller = CollaborationController(self.session)

    def local_edit(self, operation):
        plan = self.session.preview_project(operation, kind="r48.test")
        self.session.apply(plan)

    def local(self):
        snapshot = self.session.snapshot().to_dict()
        return make_revision(snapshot["content"], snapshot["project"],
                             author="alice", parents=(self.base.digest,))

    def incoming(self, operation):
        project = deepcopy(self.project)
        operation(project)
        return make_revision(self.content, project,
                             author="bob", parents=(self.base.digest,))

    @staticmethod
    def change_scene(project, key, value):
        project["story"]["scenes"][0][key] = value
        return project

    def test_disjoint_revision_merge_one_undo_and_no_disk_writes(self):
        self.local_edit(lambda p: {**p, "title": "Alice's title"})
        incoming = self.incoming(lambda p: p.update(subtitle="Bob's subtitle"))
        review = self.controller.compare(self.base, self.local(), incoming)
        self.assertTrue(review.can_apply)
        self.assertEqual(review.conflicts, ())
        self.assertEqual(review.base_digest, self.base.digest)
        transition = self.controller.apply(review, {})
        self.assertEqual(transition.snapshot.project["title"], "Alice's title")
        self.assertEqual(transition.snapshot.project["subtitle"], "Bob's subtitle")
        self.assertEqual(self.session.snapshot().dirty, True)
        self.assertEqual(self.session.storage_status()["has_destination"], False)
        previous = self.session.undo().snapshot
        self.assertEqual(previous.project["title"], "Alice's title")
        self.assertEqual(previous.project["subtitle"], self.project["subtitle"])

    def test_same_field_needs_explicit_conflict_choice(self):
        self.local_edit(lambda p: {**p, "title": "Alice"})
        incoming = self.incoming(lambda p: p.update(title="Bob"))
        review = self.controller.compare(self.base, self.local(), incoming)
        self.assertFalse(review.can_apply)
        self.assertEqual([row.path for row in review.conflicts],
                         ["/project/title"])
        before = self.session.snapshot().to_dict()
        with self.assertRaisesRegex(ValueError, "explicit decision"):
            self.controller.apply(review, {})
        self.assertEqual(self.session.snapshot().to_dict(), before)
        result = self.controller.apply(review, {"/project/title": "incoming"})
        self.assertEqual(result.snapshot.project["title"], "Bob")
        self.assertEqual(self.session.undo().snapshot.project["title"], "Alice")

    def test_scoped_scene_merge_reuses_core_semantics(self):
        self.local_edit(lambda p: self.change_scene(p, "title", "Alice title"))
        incoming = self.incoming(lambda p: self.change_scene(p, "text", "Bob text"))
        review = self.controller.compare(self.base, self.local(), incoming)
        self.assertTrue(review.can_apply)
        self.assertEqual(review.conflicts, ())
        paths = [row.path for row in review.local_changes]
        self.assertIn("/project/story/scenes/arrival/title", paths)
        result = self.controller.apply(review, {})
        scene = result.snapshot.project["story"]["scenes"][0]
        self.assertEqual(scene["title"], "Alice title")
        self.assertEqual(scene["text"], "Bob text")

    def test_two_authors_append_distinct_scenes(self):
        def append_scene(project, name):
            row = deepcopy(project["story"]["scenes"][0])
            row.update(id=name, title=name)
            project["story"]["scenes"].append(row)
            return project

        self.local_edit(lambda p: append_scene(p, "alice_scene"))
        incoming = self.incoming(lambda p: append_scene(p, "bob_scene"))
        review = self.controller.compare(self.base, self.local(), incoming)
        self.assertTrue(review.can_apply)
        result = self.controller.apply(review, {})
        self.assertEqual(
            [row["id"] for row in result.snapshot.project["story"]["scenes"]],
            ["arrival", "alice_scene", "bob_scene"])

    def test_conflicting_edit_to_same_scene_and_invalid_decision(self):
        self.local_edit(lambda p: self.change_scene(p, "title", "Alice title"))
        incoming = self.incoming(lambda p: self.change_scene(p, "title", "Bob title"))
        review = self.controller.compare(self.base, self.local(), incoming)
        self.assertEqual([row.path for row in review.conflicts],
                         ["/project/story/scenes/arrival/title"])
        with self.assertRaises(ValueError):
            self.controller.apply(review, {"/project/story/scenes/arrival/title": "both"})
        self.assertEqual(self.session.snapshot().project["story"]["scenes"][0]["title"],
                         "Alice title")
        self.assertEqual(
            self.controller.apply(
                review, {"/project/story/scenes/arrival/title": "incoming"}
            ).snapshot.project["story"]["scenes"][0]["title"],
            "Bob title")

    def test_reorder_is_a_whole_list_conflict(self):
        def append_scene(project, name):
            row = deepcopy(project["story"]["scenes"][0])
            row.update(id=name, title=name)
            project["story"]["scenes"].append(row)
            return project

        base_project = deepcopy(self.project)
        append_scene(base_project, "second")
        self.base = make_revision(self.content, base_project, author="base")
        self.session = AuthoringSession.new(self.content, base_project)
        self.controller = CollaborationController(self.session)
        self.local_edit(lambda p: {**p, "story": {
            **p["story"], "scenes": list(reversed(p["story"]["scenes"]))}})
        remote = deepcopy(base_project)
        remote["story"]["scenes"][0]["title"] = "Remote title"
        incoming = make_revision(self.content, remote, author="bob",
                                 parents=(self.base.digest,))
        review = self.controller.compare(self.base, self.local(), incoming)
        self.assertEqual([row.path for row in review.conflicts],
                         ["/project/story/scenes"])
        self.assertFalse(review.can_apply)

    def test_parent_and_invalid_revision_rejected_before_merge(self):
        incoming = self.incoming(lambda p: p.update(subtitle="new"))
        wrong = make_revision(self.content, incoming.documents()[1],
                              author="bob", parents=())
        with self.assertRaises(CollaborationError) as caught:
            self.controller.compare(self.base, self.local(), wrong)
        self.assertEqual(caught.exception.code, "unrelated_history")
        forged = replace(incoming, digest="0" * 64)
        with self.assertRaises(CollaborationError) as caught:
            self.controller.compare(self.base, self.local(), forged)
        self.assertEqual(caught.exception.code, "invalid_revision")

    def test_stale_local_revision_and_undo_aba_rejected(self):
        incoming = self.incoming(lambda p: p.update(subtitle="new"))
        review = self.controller.compare(self.base, self.local(), incoming)
        self.local_edit(lambda p: {**p, "title": "new local edit"})
        self.session.undo()
        before = self.session.snapshot().to_dict()
        with self.assertRaises(CollaborationError) as caught:
            self.controller.apply(review, {})
        self.assertEqual(caught.exception.code, "stale_local")
        self.assertEqual(self.session.snapshot().to_dict(), before)

    def test_invalid_canonical_input_and_legacy_merge_unchanged(self):
        invalid = deepcopy(self.project)
        invalid["story"]["scenes"][0]["id"] = ""
        with self.assertRaises(ValueError):
            make_revision(self.content, invalid, author="bob")
        local = deepcopy(self.project)
        incoming = deepcopy(self.project)
        self.change_scene(local, "title", "Alice")
        self.change_scene(incoming, "text", "Bob")
        legacy = preview_merge(self.content, self.project, self.content, local,
                               self.content, incoming)
        self.assertEqual([row.path for row in legacy.conflicts],
                         ["/project/story/scenes"])


if __name__ == "__main__":
    unittest.main()
