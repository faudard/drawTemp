"""R15 Creator templates, safe v1 imports and extension contract."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.export.extensions import validate_extension_manifest
from drawtemp.export.migration import import_project, migration_preview
from drawtemp.export.r15 import ExportError, preflight
from drawtemp.export.templates import TEMPLATES, create_template


class CreatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_all_templates_use_canonical_content_and_gameproject(self):
        for kind in TEMPLATES:
            with self.subTest(template=kind):
                project = create_template(kind, self.root / kind)
                report = preflight(project / "game.json")
                self.assertTrue(report["passed"], report["errors"])
                self.assertTrue((project / "game.game.json").is_file())
                with self.assertRaises(ExportError):
                    create_template(kind, project)

    def test_import_never_rewrites_original_and_copies_assets(self):
        source = create_template("jeanne", self.root / "source")
        original = (source / "game.json").read_bytes()
        preview = migration_preview(source / "game.json")
        self.assertTrue(preview["supported"], preview["errors"])
        copied = import_project(source / "game.json", self.root / "imported")
        self.assertEqual((source / "game.json").read_bytes(), original)
        self.assertEqual((copied / "originals/game.json").read_bytes(), original)
        self.assertTrue(preflight(copied / "game.json")["passed"])

    def test_unsupported_version_fails_without_creating_output(self):
        source = create_template("blank", self.root / "source")
        path = source / "game.game.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["version"] = 900
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertFalse(migration_preview(source / "game.json")["supported"])
        with self.assertRaises(ExportError):
            import_project(source / "game.json", self.root / "imported")
        self.assertFalse((self.root / "imported").exists())

    def test_declarative_plugins_do_not_execute(self):
        valid = {"api_version": 1, "id": "sample-helper", "name": "Helper",
                 "capabilities": ["asset-catalog"]}
        self.assertEqual(validate_extension_manifest(valid), valid)
        for change in ({"api_version": 3},
                       {"capabilities": ["python-exec"]},
                       {"id": "../escape"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_extension_manifest({**valid, **change})


if __name__ == "__main__":
    unittest.main()
