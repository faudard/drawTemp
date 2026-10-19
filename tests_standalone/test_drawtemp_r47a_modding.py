"""R47.A: declarative SDK mod contracts, permissions, tamper and safety cases."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.sdk.modding import (
    ModError, ModRegistry, read_mod_manifest, validate_mod_manifest,
)


def manifest(mod_id="quest-mod", namespace="org.example.quest"):
    return {
        "schema": 1, "id": mod_id, "version": "1.0.0",
        "namespace": namespace,
        "requires": {"min_api": "1.0.0", "max_api": "2.0.0",
                     "features": ["modding-declarative.v1", "project-extensions.v1"]},
        "permissions": ["project.extensions.write"],
        "dependencies": [], "resources": [],
        "extension": {"data": {"entry": "quest-1"}, "references": []},
        "rights": {"license": "MIT", "origin": "original authored sample",
                   "evidence": "author assertion (not independently approved)",
                   "redistributable": True},
    }


class ManifestTests(unittest.TestCase):
    def test_valid_copy_sdk_and_declaration_is_not_license_certification(self):
        doc = manifest()
        checked = validate_mod_manifest(doc)
        checked["extension"]["data"]["entry"] = "changed"
        self.assertEqual(doc["extension"]["data"]["entry"], "quest-1")
        status = ModRegistry().install(doc)
        self.assertFalse(status["rights_verified"])
        self.assertFalse(status["code_executed"])
        self.assertFalse(status["enabled"])

    def test_reject_executable_fields_versions_permissions_and_tampered_rights(self):
        variations = [
            ({"schema": True}, "unsupported_schema"),
            ({"version": "1.0.0-rc1"}, "invalid_version"),
            ({"permissions": ["python.exec"]}, "invalid_permissions"),
            ({"permissions": ["project.read"]}, "invalid_permissions"),
            ({"requires": {"min_api": "1.0.0", "max_api": "2.0.0", "features": []}}, "invalid_manifest"),
            ({"requires": {"min_api": "99.0.0", "max_api": "100.0.0", "features": ["modding-declarative.v1"]}}, "incompatible_sdk"),
            ({"dependencies": [{"id": "quest-mod", "min_version": "1.0.0", "max_version": "2.0.0"}]}, "invalid_dependencies"),
            ({"resources": [{"id": "art-pack", "version": "1.0.0", "sha256": "not-a-hash"}]}, "invalid_manifest"),
            ({"rights": {"license": "MIT", "origin": "local", "evidence": "?", "redistributable": "true"}}, "invalid_rights"),
            ({"entrypoint": "plugin.py"}, "invalid_manifest"),
        ]
        for changes, code in variations:
            with self.subTest(changes=changes), self.assertRaises(ModError) as err:
                validate_mod_manifest({**deepcopy(manifest()), **changes})
            self.assertEqual(err.exception.code, code)

    def test_file_limits_duplicates_symlink_and_invalid_constants(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            file = root / "valid.json"
            file.write_text(json.dumps(manifest()), encoding="utf-8")
            self.assertEqual(read_mod_manifest(file), manifest())
            for raw in ('{"schema":1,"schema":1}', '{"schema":NaN}'):
                file.write_text(raw, encoding="utf-8")
                with self.assertRaises(ModError):
                    read_mod_manifest(file)
            file.write_bytes(b"X" * 65537)
            with self.assertRaises(ModError) as err:
                read_mod_manifest(file)
            self.assertEqual(err.exception.code, "size_limit")
            link = root / "link.json"
            try:
                link.symlink_to(file)
            except (OSError, NotImplementedError):
                pass
            else:
                with self.assertRaises(ModError) as err:
                    read_mod_manifest(link)
                self.assertEqual(err.exception.code, "unsafe_path")


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.doc = manifest()
        self.registry = ModRegistry()
        self.registry.install(self.doc)
        self.editor = AuthoringSession.new(*reference_project())

    def test_fail_closed_grants_preview_apply_undo_and_no_silent_overwrite(self):
        before = self.editor.snapshot().to_dict()
        with self.assertRaises(ModError):
            self.registry.preview_extension("quest-mod", self.editor)
        for wrong in ([], ["project.read"], ["project.extensions.write", "project.extensions.write"]):
            with self.subTest(wrong=wrong), self.assertRaises(ModError):
                self.registry.enable("quest-mod", grants=wrong)
        self.registry.enable("quest-mod", grants=["project.extensions.write"])
        self.assertEqual(self.editor.snapshot().to_dict(), before)
        self.registry.preview_extension("quest-mod", self.editor)
        self.assertEqual(self.editor.snapshot().to_dict(), before)
        self.registry.apply_extension("quest-mod", self.editor, expected_revision=0)
        after = self.editor.snapshot().to_dict()
        self.assertEqual(after["project"]["extensions"]["org.example.quest"]["data"],
                         {"entry": "quest-1"})
        with self.assertRaises(ModError) as error:
            self.registry.apply_extension("quest-mod", self.editor, expected_revision=0)
        self.assertEqual(error.exception.code, "stale_revision")
        with self.assertRaises(AuthoringError) as error:
            self.registry.apply_extension("quest-mod", self.editor, expected_revision=1)
        self.assertEqual(error.exception.code, "invalid_edit")
        self.editor.undo()
        self.assertEqual(self.editor.snapshot().to_dict()["project"], before["project"])
        self.editor.redo()
        self.assertEqual(self.editor.snapshot().to_dict()["project"], after["project"])
        self.registry.disable("quest-mod")
        with self.assertRaises(ModError):
            self.registry.preview_extension("quest-mod", self.editor)

    def test_dependencies_and_safe_removal(self):
        dep = manifest("extra-mod", "org.example.extra")
        dep["dependencies"] = [{"id": "quest-mod", "min_version": "1.0.0",
                                "max_version": "2.0.0"}]
        self.registry.install(dep)
        with self.assertRaises(ModError) as caught:
            self.registry.uninstall("quest-mod", project=self.editor.snapshot())
        self.assertEqual(caught.exception.code, "dependency_in_use")
        self.assertFalse(self.registry.uninstall("extra-mod", project=self.editor.snapshot())
                         ["deleted_project_data"])
        self.registry.enable("quest-mod", grants=self.doc["permissions"])
        self.registry.apply_extension("quest-mod", self.editor, expected_revision=0)
        with self.assertRaises(ModError) as caught:
            self.registry.uninstall("quest-mod", project=self.editor.snapshot())
        self.assertEqual(caught.exception.code, "data_in_use")
        self.editor.undo()
        result = self.registry.uninstall("quest-mod", project=self.editor.snapshot())
        self.assertEqual(result["removed"], "quest-mod")
        self.assertFalse(result["deleted_asset_files"])

    def test_pack_pins_fail_closed_and_missing_dependencies(self):
        another = manifest("extra-mod", "org.example.extra")
        another["dependencies"] = [{"id": "missing-mod", "min_version": "1.0.0",
                                    "max_version": "2.0.0"}]
        with self.assertRaises(ModError) as caught:
            self.registry.install(another)
        self.assertEqual(caught.exception.code, "missing_dependency")
        another["dependencies"] = []
        another["resources"] = [{"id": "art-pack", "version": "1.0.0",
                                 "sha256": "0" * 64}]
        with self.assertRaises(ModError) as caught:
            self.registry.install(another)
        self.assertEqual(caught.exception.code, "missing_resource")
        with TemporaryDirectory() as temp:
            path = Path(temp) / "pack.zip"
            path.write_bytes(b"not a zip")
            with self.assertRaises(ModError) as caught:
                self.registry.install(another, resource_paths={"art-pack": path})
            self.assertEqual(caught.exception.code, "invalid_resource")


if __name__ == "__main__":
    unittest.main()
