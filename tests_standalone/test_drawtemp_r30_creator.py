"""R30 Creator ecosystem contracts: fail-closed packs, SDK and semantic merge."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import warnings
import zipfile

from drawtemp.sdk.capability_contracts import (
    CapabilityError, negotiate_sdk, parse_semver, require_sdk,
)
from drawtemp.export.creator_packs import (
    PackError, build_pack, inspect_pack, validate_manifest,
)
from drawtemp.sdk.semantic_review import (
    semantic_diff, preview_merge, stage_merge, fingerprint_pair,
)


def manifest_for(filename, raw):
    return {
        "schema": 1, "id": "sample-terrain", "version": "1.0.0",
        "kind": "terrain",
        "requires": {
            "min_api": "1.0.0", "max_api": "2.0.0",
            "features": ["authoring.v1"],
        },
        "files": [{
            "path": filename, "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "license": "CC0-1.0", "origin": "Original test artwork, not for release",
        }],
    }


def sample_documents():
    return (
        {"version": 1, "missions": [
            {"id": "village", "name": "Village", "board": {"width": 3},
             "triggers": [{"id": "intro", "actions": ["talk"]}]},
            {"id": "forest", "name": "Forest", "board": {"width": 2}},
        ]},
        {"version": 1, "title": "Example", "story": {"flag": False}},
    )


class CapabilityContractTests(unittest.TestCase):
    def test_current_sdk_and_unknown_capabilities(self):
        report = require_sdk(required_features=["authoring.v1"])
        self.assertTrue(report.compatible)
        self.assertIn("authoring.v1", report.available)
        self.assertEqual(report.api_version, "1.0.0")
        fail = negotiate_sdk(required_features=["realtime-movement.v99"])
        self.assertFalse(fail.compatible)
        self.assertEqual(fail.reason, "missing_features")
        with self.assertRaises(CapabilityError):
            require_sdk(required_features=["realtime-movement.v99"])

    def test_semver_range_and_bad_inputs(self):
        self.assertEqual(parse_semver("10.2.0"), (10, 2, 0))
        for invalid in ["1", "01.0.0", "1.0.0-beta", "1.0", "", None, "1.2.3.4"]:
            with self.subTest(invalid=invalid), self.assertRaises(CapabilityError):
                parse_semver(invalid)
        with self.assertRaises(CapabilityError):
            negotiate_sdk(min_api="2.0.0", max_api="2.0.0")
        self.assertEqual(negotiate_sdk(min_api="2.0.0").reason,
                         "sdk_api_out_of_range")
        with self.assertRaises(CapabilityError):
            negotiate_sdk(required_features="authoring.v1")
        with self.assertRaises(CapabilityError):
            negotiate_sdk(required_features=["authoring.v1", "authoring.v1"])


class CreatorPackTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        (self.source / "terrain").mkdir(parents=True)
        self.payload = b"\x89PNG\r\nsafe-test-bytes"
        (self.source / "terrain/grass.png").write_bytes(self.payload)
        self.manifest = manifest_for("terrain/grass.png", self.payload)

    def test_roundtrip_determinism_and_no_asset_clearance_claim(self):
        first = build_pack(self.source, self.root / "a.zip", self.manifest)
        second = build_pack(self.source, self.root / "b.zip", self.manifest)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        inspection = inspect_pack(first)
        self.assertEqual(inspection.pack_id, "sample-terrain")
        self.assertEqual(inspection.files, ("terrain/grass.png",))
        self.assertFalse(inspection.to_dict()["rights_verified"])
        self.assertFalse(inspection.to_dict()["executable"])
        untouched = first.read_bytes()
        with self.assertRaises(PackError) as error:
            build_pack(self.source, first, self.manifest)
        self.assertEqual(error.exception.code, "destination_exists")
        self.assertEqual(first.read_bytes(), untouched)

    def test_source_modified_is_refused_without_output(self):
        (self.source / "terrain/grass.png").write_bytes(b"modified")
        path = self.root / "failed.zip"
        with self.assertRaises(PackError) as error:
            build_pack(self.source, path, self.manifest)
        self.assertEqual(error.exception.code, "hash_mismatch")
        self.assertFalse(path.exists())

    def test_archive_tamper_rejects_hash_and_unlisted_files(self):
        clean = build_pack(self.source, self.root / "original.zip", self.manifest)
        with zipfile.ZipFile(clean) as archive:
            original_manifest = archive.read("manifest.json")
        with zipfile.ZipFile(self.root / "tampered.zip", "w") as archive:
            archive.writestr("manifest.json", original_manifest)
            archive.writestr("terrain/grass.png", b"wrong")
        with self.assertRaises(PackError):
            inspect_pack(self.root / "tampered.zip")
        with zipfile.ZipFile(self.root / "extra.zip", "w") as archive:
            archive.writestr("manifest.json", original_manifest)
            archive.writestr("terrain/grass.png", self.payload)
            archive.writestr("rogue.py", b"print('never execute')")
        with self.assertRaises(PackError):
            inspect_pack(self.root / "extra.zip")

    def test_manifest_rejects_traversal_duplicates_code_and_missing_rights(self):
        cases = [
            {"files": [{**self.manifest["files"][0], "path": "../escape.png"}]},
            {"files": [{**self.manifest["files"][0], "path": "evil.py"}]},
            {"files": [self.manifest["files"][0], self.manifest["files"][0]]},
            {"files": [{**self.manifest["files"][0], "license": ""}]},
            {"files": [{**self.manifest["files"][0], "origin": ""}]},
            {"requires": {**self.manifest["requires"],
                          "features": ["action-realtime.v1"]}},
            {"version": "9.0"},
        ]
        for altered in cases:
            with self.subTest(altered=altered), self.assertRaises(PackError):
                validate_manifest({**self.manifest, **altered})

    def test_archive_rejects_duplicate_members_and_duplicate_json_keys(self):
        raw = json.dumps(self.manifest).encode()
        for name, contents in (
            ("duplicate.zip", [('manifest.json', raw),
                               ('terrain/grass.png', self.payload),
                               ('terrain/grass.png', self.payload)]),
            ("duplicate-json.zip", [('manifest.json', b'{"schema":1,"schema":1}'),
                                    ('terrain/grass.png', self.payload)]),
        ):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(self.root / name, "w") as archive:
                    for path, data in contents:
                        archive.writestr(path, data)
            with self.subTest(name=name), self.assertRaises(PackError):
                inspect_pack(self.root / name)

    def test_unverified_or_wrong_source_never_alters_it(self):
        sentinel = self.source / "terrain/grass.png"
        original = sentinel.read_bytes()
        build_pack(self.source, self.root / "build.zip", self.manifest)
        self.assertEqual(sentinel.read_bytes(), original)
        self.assertFalse((self.source / "manifest.json").exists())


class SemanticReviewTests(unittest.TestCase):
    def setUp(self):
        self.base_content, self.base_project = sample_documents()

    def test_keyed_missions_and_atomic_ordered_event_actions(self):
        after = deepcopy(self.base_content)
        after["missions"][0]["name"] = "New Village"
        after["missions"][0]["triggers"][0]["actions"].append("reward")
        changes = semantic_diff(self.base_content, self.base_project,
                                after, self.base_project)
        paths = [change.path for change in changes]
        self.assertIn("/content/missions/village/name", paths)
        self.assertIn("/content/missions/village/triggers", paths)
        self.assertNotIn("/content/missions/0/name", paths)

    def test_disjoint_changes_three_way_merge_without_input_mutation(self):
        local = deepcopy(self.base_content)
        local["missions"][0]["name"] = "New Village"
        incoming = deepcopy(self.base_content)
        incoming["missions"][0]["board"]["width"] = 12
        left_copy = deepcopy(local)
        review = preview_merge(self.base_content, self.base_project,
                               local, self.base_project,
                               incoming, self.base_project)
        self.assertTrue(review.can_apply)
        self.assertEqual(review.content["missions"][0]["name"], "New Village")
        self.assertEqual(review.content["missions"][0]["board"]["width"], 12)
        self.assertEqual(local, left_copy)

    def test_same_field_and_atomic_list_conflicts(self):
        local = deepcopy(self.base_content)
        remote = deepcopy(self.base_content)
        local["missions"][0]["name"] = "Local"
        remote["missions"][0]["name"] = "Remote"
        conflict = preview_merge(self.base_content, self.base_project,
                                 local, self.base_project,
                                 remote, self.base_project)
        self.assertFalse(conflict.can_apply)
        self.assertEqual(conflict.conflicts[0].path,
                         "/content/missions/village/name")
        self.assertIsNone(conflict.content)
        local = deepcopy(self.base_content)
        remote = deepcopy(self.base_content)
        local["missions"][0]["triggers"][0]["actions"].append("open")
        remote["missions"][0]["triggers"][0]["actions"].append("close")
        result = preview_merge(self.base_content, self.base_project,
                               local, self.base_project, remote, self.base_project)
        self.assertFalse(result.can_apply)
        self.assertEqual(result.conflicts[0].path,
                         "/content/missions/village/triggers")

    def test_concurrent_reorder_is_never_silently_merged(self):
        local = deepcopy(self.base_content)
        local["missions"].reverse()
        remote = deepcopy(self.base_content)
        remote["missions"][0]["name"] = "Changed"
        review = preview_merge(self.base_content, self.base_project,
                               local, self.base_project, remote, self.base_project)
        self.assertFalse(review.can_apply)
        self.assertEqual(review.conflicts[0].path, "/content/missions")

    def test_deletion_vs_update_conflicts(self):
        local_project = deepcopy(self.base_project)
        del local_project["story"]
        remote_project = deepcopy(self.base_project)
        remote_project["story"]["flag"] = True
        result = preview_merge(self.base_content, self.base_project,
                               self.base_content, local_project,
                               self.base_content, remote_project)
        self.assertFalse(result.can_apply)
        self.assertEqual(result.conflicts[0].path, "/project/story")

    def test_real_authoring_staging_undo_and_stale_aba(self):
        from drawtemp.sdk.authoring import AuthoringSession
        from drawtemp.sdk.reference import reference_project
        content, project = reference_project()
        session = AuthoringSession.new(content, project)
        original = session.snapshot().to_dict()
        initial_content, initial_project = original["content"], original["project"]
        update = deepcopy(initial_content)
        update["missions"][0]["name"] = "Village revu"
        plan = session.preview_pair(lambda _c, p: (update, p))
        session.apply(plan)
        current = session.snapshot().to_dict()
        remote = deepcopy(initial_project)
        remote["title"] = "Projet distant"
        review = preview_merge(initial_content, initial_project,
                               current["content"], current["project"],
                               initial_content, remote)
        self.assertTrue(review.can_apply)
        changed_preview = preview_merge(initial_content, initial_project,
                                        current["content"], current["project"],
                                        initial_content, remote)
        changed_preview.project["title"] = "Unreviewed alteration"
        with self.assertRaisesRegex(ValueError, "changed after review"):
            stage_merge(session, changed_preview, expected_revision=session.revision)
        staged = stage_merge(session, review, expected_revision=session.revision)
        # Staging is not an implicit commit.
        self.assertEqual(session.snapshot().project["title"], initial_project["title"])
        session.apply(staged)
        self.assertEqual(session.snapshot().project["title"], "Projet distant")
        self.assertEqual(session.undo().snapshot.project["title"],
                         initial_project["title"])
        with self.assertRaises(ValueError):
            stage_merge(session, review, expected_revision=1)
        self.assertNotEqual(fingerprint_pair(initial_content, initial_project),
                            fingerprint_pair(update, remote))


if __name__ == "__main__":
    unittest.main()
