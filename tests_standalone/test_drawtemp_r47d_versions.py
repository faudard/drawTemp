"""R47.C safe manifest upgrade/downgrade without automatic data migration."""
from copy import deepcopy
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.modding import ModError, ModRegistry
from drawtemp.sdk.reference import reference_project
from tests_standalone.test_drawtemp_r47a_modding import manifest


class VersionReplaceTests(unittest.TestCase):
    def setUp(self):
        self.registry = ModRegistry()
        self.old = manifest()
        self.registry.install(self.old)
        self.session = AuthoringSession.new(*reference_project())
        self.registry.enable("quest-mod", grants=["project.extensions.write"])
        self.registry.apply_extension("quest-mod", self.session,
                                      expected_revision=self.session.revision)
        self.baseline = self.session.snapshot().to_dict()

    def changed(self, version):
        doc = deepcopy(self.old)
        doc["version"] = version
        return doc

    def test_upgrade_revokes_grants_preserves_data_and_reverts_explicitly(self):
        old_sha = self.registry.status("quest-mod")["manifest_sha256"]
        next_doc = self.changed("1.1.0")
        upgraded = self.registry.replace_version(
            "quest-mod", next_doc, project=self.session.snapshot())
        self.assertEqual(upgraded["previous_version"], "1.0.0")
        self.assertEqual(upgraded["version"], "1.1.0")
        self.assertFalse(upgraded["downgraded"])
        self.assertTrue(upgraded["grants_revoked"])
        self.assertFalse(upgraded["project_modified"])
        self.assertFalse(self.registry.status("quest-mod")["enabled"])
        self.assertEqual(self.registry.status("quest-mod")["grants"], [])
        self.assertNotEqual(old_sha, self.registry.status("quest-mod")["manifest_sha256"])
        self.assertEqual(self.session.snapshot().to_dict(), self.baseline)
        verified = self.registry.audit_project(
            self.session.snapshot(),
            expected_pins={"quest-mod": self.registry.status("quest-mod")["manifest_sha256"]})
        self.assertTrue(verified["compatible"], verified["errors"])
        with self.assertRaises(ModError) as denied:
            self.registry.replace_version(
                "quest-mod", self.old, project=self.session.snapshot())
        self.assertEqual(denied.exception.code, "downgrade_denied")
        self.registry.enable("quest-mod", grants=["project.extensions.write"])
        rollback = self.registry.replace_version(
            "quest-mod", self.old, project=self.session.snapshot(),
            allow_downgrade=True)
        self.assertTrue(rollback["downgraded"])
        self.assertEqual(self.registry.status("quest-mod")["manifest_sha256"], old_sha)
        self.assertFalse(self.registry.status("quest-mod")["enabled"])
        self.assertEqual(self.session.snapshot().to_dict(), self.baseline)

    def test_fail_closed_changes_are_atomic(self):
        choices = [
            ("1.0.0", None, "same_version"),
            ("0.9.0", None, "downgrade_denied"),
            ("1.1.0", ("id", "other-mod"), "identity_changed"),
            ("1.1.0", ("namespace", "org.example.other"), "identity_changed"),
            ("1.1.0", ("extension", None), "migration_required"),
            ("1.1.0", ("extension", {"data": {"entry": "mutated"},
                                    "references": []}), "migration_required"),
            ("1.1.0", ("dependencies", [{
                "id": "missing-mod", "min_version": "1.0.0",
                "max_version": "2.0.0"}]), "missing_dependency"),
        ]
        for version, edit, code in choices:
            with self.subTest(code=code, edit=edit):
                candidate = self.changed(version)
                if edit:
                    candidate[edit[0]] = edit[1]
                before = self.registry.status("quest-mod")
                with self.assertRaises(ModError) as error:
                    self.registry.replace_version(
                        "quest-mod", candidate, project=self.session.snapshot())
                self.assertEqual(error.exception.code, code)
                self.assertEqual(self.registry.status("quest-mod"), before)
                self.assertEqual(self.session.snapshot().to_dict(), self.baseline)

    def test_existing_dependent_blocks_incompatible_upgrade(self):
        dependent = manifest("dependent-mod", "org.example.dependent")
        dependent["dependencies"] = [{
            "id": "quest-mod", "min_version": "1.0.0", "max_version": "1.5.0"}]
        self.registry.install(dependent)
        before = self.registry.statuses()
        with self.assertRaises(ModError) as error:
            self.registry.replace_version(
                "quest-mod", self.changed("2.0.0"),
                project=self.session.snapshot())
        self.assertEqual(error.exception.code, "incompatible_dependent")
        self.assertEqual(self.registry.statuses(), before)
        upgraded = self.registry.replace_version(
            "quest-mod", self.changed("1.4.0"),
            project=self.session.snapshot())
        self.assertEqual(upgraded["version"], "1.4.0")

    def test_preexisting_namespace_drift_and_invalid_project_rejected(self):
        before = self.registry.status("quest-mod")
        tampered = deepcopy(self.baseline)
        tampered["project"]["extensions"]["org.example.quest"]["data"]["entry"] = "changed"
        with self.assertRaises(ModError) as mismatch:
            self.registry.replace_version(
                "quest-mod", self.changed("1.1.0"), project=tampered)
        self.assertEqual(mismatch.exception.code, "data_in_use")
        with self.assertRaises(ModError) as invalid:
            self.registry.replace_version(
                "quest-mod", self.changed("1.1.0"), project={})
        self.assertEqual(invalid.exception.code, "invalid_project")
        self.assertEqual(before, self.registry.status("quest-mod"))

    def test_no_resources_can_be_invented_or_granted_at_version_change(self):
        forged = self.changed("1.1.0")
        forged["resources"] = [{
            "id": "missing-pack", "version": "1.0.0", "sha256": "0" * 64}]
        with self.assertRaises(ModError) as error:
            self.registry.replace_version(
                "quest-mod", forged, project=self.session.snapshot())
        self.assertEqual(error.exception.code, "missing_resource")
        self.assertTrue(self.registry.status("quest-mod")["enabled"])


if __name__ == "__main__":
    unittest.main()
