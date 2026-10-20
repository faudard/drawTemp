"""R47.E: grant/preview/apply must recheck R30 packs and dependency closure."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.modding import ModError, ModRegistry
from drawtemp.export.templates import create_template
from tests_standalone.test_drawtemp_r47c_two_games import setup_registry


class LiveIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        directory = create_template("tactical", self.root / "game")
        self.editor = AuthoringSession.open(directory / "game.json")
        self.registry, self.mods, self.archives, self.pins = setup_registry(
            self.root / "packs")

    def corrupt(self, doc):
        archive = next(iter(self.archives[doc["id"]].values()))
        original = archive.read_bytes()
        archive.write_bytes(b"untrusted replacement")
        return archive, original

    def test_tampering_between_install_and_consent_is_rejected(self):
        target = self.mods[0]
        baseline = self.editor.snapshot().to_dict()
        archive, original = self.corrupt(target)
        with self.assertRaises(ModError) as err:
            self.registry.enable(target["id"], grants=target["permissions"])
        self.assertEqual(err.exception.code, "resource_changed")
        self.assertFalse(self.registry.status(target["id"])["enabled"])
        self.assertEqual(self.registry.status(target["id"])["grants"], [])
        self.assertEqual(baseline, self.editor.snapshot().to_dict())
        archive.write_bytes(original)
        verified = self.registry.verify_runtime(target["id"])
        self.assertTrue(verified["integrity_verified"])
        self.assertFalse(verified["rights_verified"])
        self.registry.enable(target["id"], grants=target["permissions"])

    def test_tampering_after_consent_prevents_preview_and_apply(self):
        target = self.mods[0]
        self.registry.enable(target["id"], grants=target["permissions"])
        baseline = self.editor.snapshot().to_dict()
        archive, original = self.corrupt(target)
        with self.assertRaises(ModError) as preview:
            self.registry.preview_extension(target["id"], self.editor)
        self.assertEqual(preview.exception.code, "resource_changed")
        with self.assertRaises(ModError) as apply:
            self.registry.apply_extension(target["id"], self.editor,
                                          expected_revision=self.editor.revision)
        self.assertEqual(apply.exception.code, "resource_changed")
        self.assertEqual(self.editor.snapshot().to_dict(), baseline)
        self.assertEqual(self.editor.revision, baseline["revision"])
        # Audit a detached candidate with the namespace present so a missing
        # contribution cannot mask the pack integrity diagnostic.
        candidate = deepcopy(baseline)
        candidate["project"].setdefault("extensions", {})[target["namespace"]] = {
            "schema_version": 1, **deepcopy(target["extension"])}
        report = self.registry.audit_project(candidate, expected_pins=self.pins)
        self.assertFalse(report["compatible"])
        self.assertIn("resource_changed", " ".join(report["errors"]))
        archive.write_bytes(original)
        self.registry.preview_extension(target["id"], self.editor)
        self.registry.apply_extension(target["id"], self.editor,
                                      expected_revision=self.editor.revision)
        self.assertIn(target["namespace"],
                      self.editor.snapshot().to_dict()["project"]["extensions"])

    def test_tampered_required_pack_blocks_dependent_mod(self):
        parent, child = self.mods
        dependent = deepcopy(child)
        dependent["dependencies"] = [{
            "id": parent["id"], "min_version": "1.0.0",
            "max_version": "2.0.0"}]
        staged = ModRegistry()
        staged.install(parent, resource_paths=self.archives[parent["id"]])
        staged.install(dependent, resource_paths=self.archives[child["id"]])
        staged.enable(dependent["id"], grants=dependent["permissions"])
        archive, original = self.corrupt(parent)
        baseline = self.editor.snapshot().to_dict()
        with self.assertRaises(ModError) as err:
            staged.preview_extension(dependent["id"], self.editor)
        self.assertEqual(err.exception.code, "resource_changed")
        self.assertEqual(baseline, self.editor.snapshot().to_dict())
        with self.assertRaises(ModError) as err:
            staged.enable(dependent["id"], grants=dependent["permissions"])
        self.assertEqual(err.exception.code, "resource_changed")
        archive.write_bytes(original)
        staged.preview_extension(dependent["id"], self.editor)

    def test_corrupted_dependency_prevents_new_install(self):
        parent, child = self.mods
        archive, original = self.corrupt(parent)
        new = deepcopy(child)
        new["id"] = "new-child"
        new["namespace"] = "org.example.r47.newchild"
        new["dependencies"] = [{
            "id": parent["id"], "min_version": "1.0.0",
            "max_version": "2.0.0"}]
        with self.assertRaises(ModError) as err:
            self.registry.install(new, resource_paths=self.archives[child["id"]])
        self.assertEqual(err.exception.code, "resource_changed")
        self.assertEqual(len(self.registry.statuses()), 2)
        archive.write_bytes(original)
        self.registry.install(new, resource_paths=self.archives[child["id"]])
        self.assertEqual(len(self.registry.statuses()), 3)


if __name__ == "__main__":
    unittest.main()
