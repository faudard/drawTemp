"""R24.A: SDK negotiation and canonical, inert, namespaced extension data."""
import json
import math
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path

from drawtemp.core import GameProject
from drawtemp.sdk import (
    AuthoringSession, SDKCompatibilityError, ProjectExtensionError,
    capabilities, negotiate_sdk, validate_project_extensions,
)
from drawtemp.sdk.reference import reference_project
from sporebound.game_session import gameplay_project_digest


class SDKVersionTests(unittest.TestCase):
    def test_version_features_and_legacy_contract(self):
        info = capabilities()
        self.assertEqual(info["api_version"], [1, 0])
        self.assertEqual(info["project_schema"], 1)
        self.assertIn("project-extensions.v1", info["features"])
        selected = negotiate_sdk((1, 0), required_features=["project-extensions.v1"])
        self.assertEqual(selected["features"], ["project-extensions.v1"])
        selected["features"].append("fake")
        self.assertNotIn("fake", capabilities()["features"])

    def test_negotiation_fail_closed(self):
        cases = [
            ((2, 0), (), "incompatible_major"),
            ((1, 1), (), "unsupported_minor"),
            ((True, 0), (), "invalid_version"),
            ((1, -1), (), "invalid_version"),
            ((1, 0), ("not-in-sdk",), "missing_feature"),
            ((1, 0), ("replay.v1", "replay.v1"), "invalid_features"),
        ]
        for version, features, code in cases:
            with self.subTest(version=version, features=features):
                with self.assertRaises(SDKCompatibilityError) as caught:
                    negotiate_sdk(version, required_features=features)
                self.assertEqual(caught.exception.code, code)


class ProjectExtensionTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()
        self.base = self.project.to_dict()
        self.envelope = {
            "schema_version": 1,
            "data": {"chapter": 3, "tags": ["forest", "castle"]},
            "references": [{"kind": "campaign", "id": "main"}],
        }

    def extended(self):
        project = deepcopy(self.base)
        project["extensions"] = {"org.example.quest": deepcopy(self.envelope)}
        return project

    def test_legacy_project_bytes_and_digest_unchanged(self):
        self.assertNotIn("extensions", self.base)
        restored = GameProject.from_dict(deepcopy(self.base), self.content)
        self.assertEqual(restored.to_dict(), self.base)
        self.assertEqual(gameplay_project_digest(restored),
                         gameplay_project_digest(self.project))

    def test_extension_roundtrip_detached_and_validated(self):
        doc = self.extended()
        model = GameProject.from_dict(doc, self.content)
        self.assertEqual(model.to_dict(), doc)
        doc["extensions"]["org.example.quest"]["data"]["chapter"] = 999
        self.assertEqual(model.extensions["org.example.quest"]["data"]["chapter"], 3)
        extracted = model.to_dict()
        extracted["extensions"]["org.example.quest"]["data"]["tags"].append("modified")
        self.assertEqual(model.extensions["org.example.quest"]["data"]["tags"],
                         ["forest", "castle"])
        self.assertNotEqual(gameplay_project_digest(model),
                            gameplay_project_digest(self.project))
        validated = validate_project_extensions(model.extensions, content=self.content,
                                                campaigns=self.project.campaigns)
        validated["org.example.quest"]["data"]["chapter"] = 99
        self.assertEqual(model.extensions["org.example.quest"]["data"]["chapter"], 3)

    def test_bad_envelopes_and_references_rejected(self):
        base = self.extended()
        mutations = [
            ("../bad", self.envelope, "invalid_namespace"),
            ("org.example.bad", {"schema_version": 2, "data": {}}, "unsupported_schema"),
            ("org.example.bad", {"schema_version": True, "data": {}}, "unsupported_schema"),
            ("org.example.bad", {"schema_version": 1, "data": {}, "unsafe": True}, "invalid_envelope"),
            ("org.example.bad", {"schema_version": 1, "data": {"NaN": float("nan")}}, "invalid_payload"),
            ("org.example.bad", {"schema_version": 1, "data": {"x": set()}}, "invalid_payload"),
            ("org.example.bad", {"schema_version": 1, "data": {},
                                 "references": [{"kind": "mission", "id": "unknown"}]}, "invalid_reference"),
            ("org.example.bad", {"schema_version": 1, "data": {},
                                 "references": [{"kind": "python", "id": "execute"}]}, "invalid_reference"),
        ]
        for namespace, envelope, code in mutations:
            with self.subTest(namespace=namespace, code=code):
                doc = deepcopy(base)
                doc["extensions"] = {namespace: deepcopy(envelope)}
                with self.assertRaises(ProjectExtensionError) as caught:
                    GameProject.from_dict(doc, self.content)
                self.assertEqual(caught.exception.code, code)
        oversized = self.extended()
        oversized["extensions"]["org.example.quest"]["data"] = {"text": "a" * 66000}
        with self.assertRaises(ProjectExtensionError) as caught:
            GameProject.from_dict(oversized, self.content)
        self.assertEqual(caught.exception.code, "size_limit")

    def test_transactional_apply_undo_redo_and_rejected_preview(self):
        editor = AuthoringSession.new(self.content, self.project)
        original = editor.snapshot().to_dict()["project"]
        def edit(project):
            project["extensions"] = {"org.example.quest": deepcopy(self.envelope)}
            return project
        plan = editor.preview_project(edit, kind="r24-extension")
        self.assertEqual(editor.snapshot().to_dict()["project"], original)
        editor.apply(plan)
        self.assertEqual(editor.snapshot().to_dict()["project"], self.extended())
        editor.undo()
        self.assertEqual(editor.snapshot().to_dict()["project"], original)
        editor.redo()
        self.assertEqual(editor.snapshot().to_dict()["project"], self.extended())
        stale = editor.snapshot().to_dict()
        with self.assertRaises(Exception):
            editor.preview_project(lambda project: {
                **project,
                "extensions": {"org.example.quest": {"schema_version": 999, "data": {}}}
            })
        self.assertEqual(editor.snapshot().to_dict(), stale)

    def test_headless_api_no_gui_modules(self):
        program = """
import sys
class Block:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in ("tkinter", "_tkinter", "PySide6", "PyQt5", "PyQt6"):
            raise AssertionError(fullname)
sys.meta_path.insert(0, Block())
from drawtemp.sdk import negotiate_sdk, validate_project_extensions
assert negotiate_sdk([1, 0])["api_version"] == [1, 0]
"""
        subprocess.run([sys.executable, "-c", program], check=True,
                       capture_output=True, text=True,
                       cwd=Path(__file__).resolve().parents[1])


if __name__ == "__main__":
    unittest.main()
