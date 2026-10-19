"""R30.C headless creator review: decisions, revisions, external-file safety."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.export.creator_packs import build_pack
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.semantic_review import resolve_merge
from drawtemp.studio.r30_creator_review import (
    MergeReviewController, PackReviewController, ReviewError,
)
from tests_standalone.test_drawtemp_r30b_pack_import import _manifest, _png


class HeadlessR30CReviewTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.content, self.project = reference_project()
        self.base = self.root / "base/game.json"
        self.base.parent.mkdir()
        AuthoringSession.new(self.content, self.project).save_as(self.base)
        self.incoming = self.root / "incoming/game.json"
        self.incoming.parent.mkdir()
        self.incoming_session = AuthoringSession.new(self.content, self.project)
        self.local_session = AuthoringSession.new(self.content, self.project)
        self.merge = MergeReviewController(self.local_session)

    def _set_title(self, session, title):
        session.apply(session.preview_project(
            lambda project: {**project, "title": title}))

    def _save_incoming(self):
        self.incoming_session.save_as(self.incoming)

    def test_conflict_requires_all_choices_and_keeps_undo(self):
        self._set_title(self.local_session, "Locally changed")
        self._set_title(self.incoming_session, "Incoming changed")
        self._save_incoming()
        prior = self.local_session.snapshot().to_dict()
        result = self.merge.compare(self.base, self.incoming)
        self.assertEqual(len(result.conflicts), 1)
        path = result.conflicts[0].path
        self.assertEqual(path, "/project/title")
        self.assertEqual(self.local_session.snapshot().to_dict(), prior)
        with self.assertRaisesRegex(ValueError, "decision"):
            self.merge.apply({})
        self.assertEqual(self.local_session.snapshot().to_dict(), prior)
        with self.assertRaisesRegex(ValueError, "local or incoming"):
            self.merge.apply({path: "ours-and-theirs"})
        self.assertEqual(self.local_session.snapshot().to_dict(), prior)
        changed = self.merge.apply({path: "incoming"})
        self.assertEqual(changed.snapshot.project["title"], "Incoming changed")
        self.assertEqual(self.local_session.undo().snapshot.project["title"],
                         "Locally changed")
        with self.assertRaises(ReviewError) as error:
            self.merge.apply({path: "local"})
        self.assertEqual(error.exception.code, "no_review")

    def test_keep_local_branch_after_review(self):
        self._set_title(self.local_session, "Local name")
        self._set_title(self.incoming_session, "Remote name")
        self._set_title(self.incoming_session, "Remote name II")
        self._save_incoming()
        self.merge.compare(self.base, self.incoming)
        with self.assertRaisesRegex(ValueError, "unchanged"):
            # Review is safe, but a choice that makes no changes is not a valid
            # canonical R1 authoring transaction.
            self.merge.apply({"/project/title": "local"})
        self.assertEqual(self.local_session.snapshot().project["title"], "Local name")

    def test_external_modified_base_and_incoming_rejected(self):
        self._set_title(self.incoming_session, "Incoming changed")
        self._save_incoming()
        self.merge.compare(self.base, self.incoming)
        before = self.local_session.snapshot().to_dict()
        self.base.write_bytes(self.base.read_bytes() + b" ")
        with self.assertRaises(ReviewError) as error:
            self.merge.apply({})
        self.assertEqual(error.exception.code, "external_change")
        self.assertEqual(self.local_session.snapshot().to_dict(), before)
        self.merge.compare(self.base, self.incoming)
        self.incoming.write_bytes(self.incoming.read_bytes() + b" ")
        with self.assertRaises(ReviewError):
            self.merge.apply({})
        self.assertEqual(self.local_session.snapshot().to_dict(), before)

    def test_changed_editor_revision_rejected_without_clobber(self):
        self._set_title(self.incoming_session, "Remote")
        self._save_incoming()
        self.merge.compare(self.base, self.incoming)
        self._set_title(self.local_session, "Newer local edit")
        current = self.local_session.snapshot().to_dict()
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.merge.apply({})
        self.assertEqual(self.local_session.snapshot().to_dict(), current)

    def test_disjoint_merge_uses_same_canonical_session(self):
        self._set_title(self.local_session, "Local")
        self.incoming_session.apply(self.incoming_session.preview_project(
            lambda project: {**project, "subtitle": "New subtitle"}))
        self._save_incoming()
        review = self.merge.compare(self.base, self.incoming)
        self.assertEqual(len(review.conflicts), 0)
        changed = self.merge.apply({})
        self.assertEqual(changed.snapshot.project["title"], "Local")
        self.assertEqual(changed.snapshot.project["subtitle"], "New subtitle")
        self.assertTrue(changed.snapshot.can_undo)
        self.assertEqual(self.local_session.undo().snapshot.project["subtitle"],
                         self.project.subtitle)

    def test_invalid_selection_and_unknown_conflict_fails_closed(self):
        self._set_title(self.local_session, "Local")
        self._set_title(self.incoming_session, "Remote")
        self._save_incoming()
        before = self.local_session.snapshot().to_dict()
        with self.assertRaisesRegex(ValueError, "explicit decision"):
            resolve_merge(self.content.to_dict(), self.project.to_dict(),
                          before["content"], before["project"],
                          self.content.to_dict(),
                          self.incoming_session.snapshot().to_dict()["project"],
                          {"/project/title": "local", "/other": "incoming"})
        self.assertEqual(self.local_session.snapshot().to_dict(), before)

    def test_pack_review_inspection_and_stale_archive(self):
        pack_source = self.root / "pack-source"
        (pack_source / "terrain").mkdir(parents=True)
        png = _png()
        (pack_source / "terrain/grass.png").write_bytes(png)
        manifest = _manifest(png)
        pack = build_pack(pack_source, self.root / "pack.zip", manifest)
        controller = PackReviewController(self.base)
        rows = controller.inspect(pack)
        self.assertEqual(rows[0].path, "terrain/grass.png")
        self.assertEqual(rows[0].kinds, ("sprite", "portrait"))
        self.assertEqual(rows[0].license, "CC0-1.0")
        choices = [{"path": "terrain/grass.png",
                    "kind": "sprite", "name": "grass"}]
        preview = controller.preview(choices)
        self.assertFalse(preview.to_dict()["rights_verified"])
        self.assertFalse((self.root / "game-out").exists())
        pack.write_bytes(pack.read_bytes() + b"altered")
        with self.assertRaises(ValueError):
            controller.publish(self.root / "game-out")
        self.assertFalse((self.root / "game-out").exists())

    def test_pack_controller_requires_explicit_review(self):
        controller = PackReviewController(self.base)
        with self.assertRaises(ReviewError) as caught:
            controller.publish(self.root / "game-out")
        self.assertEqual(caught.exception.code, "no_preview")


if __name__ == "__main__":
    unittest.main()
