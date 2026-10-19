"""R30.E: canonical scene gallery, collision protection, preview, Undo and no disk writes."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r30_scene_gallery import (
    GalleryController, GalleryError, gallery_entries, load_catalog, validate_catalog,
)
from sporebound.studio_transaction import validate_pair


class GalleryTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()
        self.session = AuthoringSession.new(self.content, self.project)
        self.gallery = GalleryController(self.session)

    def test_catalog_four_original_genre_snippets_not_complete_games(self):
        entries = gallery_entries()
        self.assertEqual(len(entries), 4)
        self.assertEqual({item.genre for item in entries},
                         {"srpg", "action-adventure", "classic-rpg", "hybrid"})
        self.assertTrue(all(item.readiness == "narrative-scene-only" for item in entries))
        self.assertTrue(all(not item.to_dict()["playable_genre_certified"]
                            for item in entries))
        self.assertEqual(load_catalog(), validate_catalog(load_catalog()))

    def test_roundtrip_all_examples_without_touching_tactical_content(self):
        original = self.session.snapshot().to_dict()
        for index, entry in enumerate(gallery_entries()):
            preview = self.gallery.preview(entry.template_id, "sample")
            self.assertEqual(len(preview.scene_ids), entry.scene_count)
            self.assertEqual(preview.source_revision, self.session.revision)
            self.assertEqual(self.session.snapshot().to_dict()["project"],
                             original["project"])
            after = self.gallery.apply(preview).snapshot.to_dict()
            content, project = validate_pair(after["content"], after["project"])
            self.assertEqual(content, original["content"])
            self.assertEqual(len(project["story"]["scenes"]),
                             len(original["project"]["story"]["scenes"]) +
                             entry.scene_count)
            self.assertEqual(self.session.undo().snapshot.to_dict()["project"],
                             original["project"])
            self.session.redo()
            self.session.undo()
            self.assertFalse(self.session.snapshot().dirty)
        self.assertEqual(self.session.snapshot().to_dict()["project"],
                         original["project"])

    def test_namespace_reuse_in_two_projects_and_duplicate_rejection(self):
        one = self.gallery.preview("forest", "alpha")
        self.gallery.apply(one)
        two = self.gallery.preview("forest", "beta")
        after = self.gallery.apply(two).snapshot.to_dict()
        ids = {scene["id"] for scene in after["project"]["story"]["scenes"]}
        self.assertTrue(set(one.scene_ids).issubset(ids))
        self.assertTrue(set(two.scene_ids).issubset(ids))
        self.assertFalse(set(one.scene_ids) & set(two.scene_ids))
        with self.assertRaises(GalleryError) as caught:
            self.gallery.preview("forest", "alpha")
        self.assertEqual(caught.exception.code, "duplicate_scene")
        self.assertEqual(self.session.snapshot().to_dict()["project"], after["project"])
        other = AuthoringSession.new(self.content, self.project)
        template = GalleryController(other).preview("forest", "alpha")
        self.assertEqual(template.scene_ids, one.scene_ids)

    def test_existing_campaign_intro_is_never_clobbered(self):
        with self.assertRaises(GalleryError) as caught:
            self.gallery.preview("tactical", "intro", campaign_id="main")
        self.assertEqual(caught.exception.code, "existing_entry")
        self.assertEqual(self.session.snapshot().project["story"]["entry_scenes"]["main"],
                         "arrival")

    def test_optional_campaign_entry_link_is_explicit_and_valid(self):
        base = self.project.to_dict()
        base["story"]["entry_scenes"] = {}
        session = AuthoringSession.new(self.content, base)
        controller = GalleryController(session)
        preview = controller.preview("tactical", "demo", campaign_id="main")
        after = controller.apply(preview).snapshot.to_dict()
        self.assertEqual(after["project"]["story"]["entry_scenes"]["main"],
                         preview.scene_ids[0])
        self.assertEqual(after["content"], self.content.to_dict())
        self.assertTrue(session.undo().snapshot.can_redo)

    def test_existing_files_remain_until_explicit_session_save(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "game.json"
            AuthoringSession.new(self.content, self.project).save_as(path)
            session = AuthoringSession.open(path)
            controller = GalleryController(session)
            prior = (path.read_bytes(), path.with_name("game.game.json").read_bytes())
            preview = controller.preview("bridge", "sample")
            self.assertEqual((path.read_bytes(),
                              path.with_name("game.game.json").read_bytes()), prior)
            controller.apply(preview)
            self.assertEqual((path.read_bytes(),
                              path.with_name("game.game.json").read_bytes()), prior)
            session.save()
            new_project = json.loads(path.with_name("game.game.json").read_text())
            self.assertIn(preview.scene_ids[0],
                          [scene["id"] for scene in new_project["story"]["scenes"]])

    def test_stale_preview_and_invalidation_fail_closed(self):
        stale = self.gallery.preview("forest", "one")
        other = self.gallery.preview("inn", "two")
        with self.assertRaises(GalleryError):
            self.gallery.apply(stale)
        self.gallery.invalidate()
        with self.assertRaises(GalleryError):
            self.gallery.apply(other)
        stale = self.gallery.preview("forest", "one")
        self.session.apply(self.session.preview_project(
            lambda project: {**project, "title": "New edit"}))
        current = self.session.snapshot().to_dict()
        with self.assertRaises(AuthoringError) as caught:
            self.gallery.apply(stale)
        self.assertEqual(caught.exception.code, "stale_revision")
        self.assertEqual(self.session.snapshot().to_dict(), current)

    def test_bad_namespace_unknown_template_campaign_and_catalog_rejected(self):
        for tpl, ns, campaign in (
            ("missing", "good", None), ("forest", "../bad", None),
            ("forest", "CAPS", None), ("forest", "", None),
            ("forest", "good", "unknown"),
        ):
            with self.subTest(tpl=tpl, namespace=ns), self.assertRaises(GalleryError):
                self.gallery.preview(tpl, ns, campaign_id=campaign)
        self.assertEqual(self.session.revision, 0)
        original = load_catalog()
        bad = []
        sample = deepcopy(original)
        sample["entries"][0]["scenes"][0]["choices"][0]["effects"] = []
        bad.append(sample)
        sample = deepcopy(original)
        sample["entries"][0]["scenes"][0]["choices"][0]["next_scene"] = "missing"
        bad.append(sample)
        sample = deepcopy(original)
        sample["entries"][0]["scenes"][1]["choices"][0]["next_scene"] = "briefing"
        bad.append(sample)
        sample = deepcopy(original)
        sample["entries"].append(deepcopy(sample["entries"][0]))
        bad.append(sample)
        sample = deepcopy(original)
        sample["entries"][0]["readiness"] = "certified-action-rpg"
        bad.append(sample)
        sample = deepcopy(original)
        sample["entries"][0]["genre"] = ["srpg"]
        bad.append(sample)
        for candidate in bad:
            with self.assertRaises(GalleryError):
                validate_catalog(candidate)


if __name__ == "__main__":
    unittest.main()
