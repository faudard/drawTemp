"""Installer regression tests: valid portable demo and corrupt/untrusted ZIPs."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
def load(path, name):
    spec = spec_from_file_location(name, ROOT / path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

imp = load("scripts/import_watercolor_sheets.py", "watercolor_source")
installer = load("scripts/install_watercolor_pack.py", "watercolor_install")
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


def prepare(root, *, corrupt=False):
    sprites = [
        {"id": f"{group}_{pose}", "path": f"sprites/{group}/{pose}.png"}
        for group, _, _, _, poses in imp.SHEETS
        for pose in (poses.split() if isinstance(poses, str) else poses)
    ]
    index = {"schema_version": 1, "sprites": sprites}
    manifest = imp.build_registry(sprites)
    if corrupt:
        manifest["entries"][-1]["id"] = manifest["entries"][0]["id"]
    pack = root / "art.zip"
    with ZipFile(pack, "w") as archive:
        archive.writestr("assets/watercolor/index.json", json.dumps(index))
        archive.writestr("assets/watercolor/registry.json", json.dumps(manifest))
        for sprite in sprites:
            archive.writestr("assets/watercolor/" + sprite["path"], PNG)
    content = root / "jeanne.json"
    content.write_text(json.dumps({
        "missions": [{"units": [{"id": "jeanne"}, {"id": "lancier_pont"},
                                {"id": "agnes"}, {"id": "bandit_hospice"}]}]
    }), encoding="utf-8")
    project = root / "jeanne.game.json"
    project.write_text(json.dumps({"version": 1, "title": "Jeanne Test"}),
                       encoding="utf-8")
    return pack, content, project


class WatercolorInstallerTests(unittest.TestCase):
    def test_unique_ids_and_safe_bundle(self):
        with TemporaryDirectory() as tmp:
            pack, _, _ = prepare(Path(tmp))
            with ZipFile(pack) as archive:
                entries, paths = installer.validate_bundle(archive)
            self.assertEqual(len(entries), 103)
            self.assertEqual(len(paths), 88)

    def test_corrupt_duplicate_animation_id_rejected(self):
        with TemporaryDirectory() as tmp:
            pack, content, project = prepare(Path(tmp), corrupt=True)
            target = Path(tmp) / "output"
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                installer.install(pack, content, project, target)
            self.assertFalse(target.exists())

    def test_installer_creates_relocatable_game_without_modifying_input(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack, content, project = prepare(root)
            original = project.read_bytes()
            target = root / "output"
            installed = installer.install(pack, content, project, target)
            self.assertTrue(installed.is_file())
            self.assertEqual(project.read_bytes(), original)
            self.assertEqual(len(list((target / "assets/watercolor/sprites").rglob("*.png"))), 88)
            from sporebound.assets import AssetRegistry
            assets = json.loads(installed.read_text(encoding="utf-8"))["assets"]
            registry = AssetRegistry(assets)
            self.assertEqual(registry.diagnostics(target), [])
            self.assertEqual(registry.binding("sprite", "agnes")["id"],
                             "heroes_healer")
            self.assertEqual(registry.binding("animation", "jeanne_move")["id"],
                             "anim_jeanne_walk")
            self.assertEqual(registry.binding("animation", "jeanne_defeat")["id"],
                             "anim_jeanne_ko")
            with self.assertRaises(FileExistsError):
                installer.install(pack, content, project, target)


if __name__ == "__main__":
    unittest.main()
