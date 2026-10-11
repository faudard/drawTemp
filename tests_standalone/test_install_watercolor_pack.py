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
# A valid 1x1 RGBA PNG: guards must inspect real IHDR bytes, not just magic.
import struct
import zlib


def _chunk(tag, payload):
    data = tag + payload
    return (struct.pack(">I", len(payload)) + data +
            struct.pack(">I", zlib.crc32(data) & 0xFFFFFFFF))


PNG = (b"\x89PNG\r\n\x1a\n" +
       _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)) +
       _chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\xff")) +
       _chunk(b"IEND", b""))


def prepare(root, *, corrupt=False, wrong_dimensions=False, broken_frame=False):
    sprites = [
        {"id": f"{group}_{pose}", "path": f"sprites/{group}/{pose}.png"}
        for group, _, _, _, poses in imp.SHEETS
        for pose in (poses.split() if isinstance(poses, str) else poses)
    ]
    if wrong_dimensions:
        sprites[0]["frame_size"] = [999, 999]
    index = {"schema_version": 1, "sprites": sprites}
    manifest = imp.build_registry(sprites)
    if corrupt:
        manifest["entries"][-1]["id"] = manifest["entries"][0]["id"]
    if broken_frame:
        manifest["entries"][-1]["frames"][0]["sprite"] = "missing_sprite"
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

    def test_png_header_and_frame_size_checked_before_install(self):
        with TemporaryDirectory() as tmp:
            pack, content, project = prepare(Path(tmp), wrong_dimensions=True)
            output = Path(tmp) / "bad_dimensions"
            with self.assertRaisesRegex(ValueError, "dimensions mismatch"):
                installer.install(pack, content, project, output)
            self.assertFalse(output.exists())

    def test_animation_references_verified_before_install(self):
        from sporebound.model import RuleError
        with TemporaryDirectory() as tmp:
            pack, content, project = prepare(Path(tmp), broken_frame=True)
            output = Path(tmp) / "bad_animation"
            with self.assertRaises(RuleError):
                installer.install(pack, content, project, output)
            self.assertFalse(output.exists())

    def test_duplicate_zip_entries_rejected(self):
        import warnings
        with TemporaryDirectory() as tmp:
            pack, content, project = prepare(Path(tmp))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with ZipFile(pack, "a") as archive:
                    archive.writestr("assets/watercolor/sprites/wolf/idle.png", PNG)
            output = Path(tmp) / "duplicate_zip"
            with self.assertRaisesRegex(ValueError, "Duplicate ZIP member"):
                installer.install(pack, content, project, output)
            self.assertFalse(output.exists())

    def test_existing_jeanne_art_is_preserved_and_preview_bindings_win(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack, content, project = prepare(root)
            original_art = root / "art/jeanne/legacy.png"
            original_art.parent.mkdir(parents=True)
            original_art.write_bytes(PNG)
            game = json.loads(project.read_text(encoding="utf-8"))
            game["assets"] = {
                "version": 1,
                "entries": [
                    {"id": "legacy_jeanne", "kind": "sprite",
                     "path": "art/jeanne/legacy.png"},
                    {"id": "legacy_jeanne_move", "kind": "animation",
                     "loop": True, "frames": [
                         {"sprite": "legacy_jeanne", "duration_ms": 100}]},
                ],
                "bindings": {
                    "sprite": {"jeanne": "legacy_jeanne"},
                    "animation": {
                        "jeanne_move_south": "legacy_jeanne_move",
                        "jeanne_idle_south": "legacy_jeanne_move",
                    },
                },
            }
            project.write_text(json.dumps(game), encoding="utf-8")
            original_bytes = project.read_bytes()
            output = root / "preview"
            output_project = installer.install(pack, content, project, output)
            self.assertEqual(original_bytes, project.read_bytes())
            self.assertEqual((output / "art/jeanne/legacy.png").read_bytes(), PNG)
            from sporebound.assets import AssetRegistry
            registry = AssetRegistry(json.loads(
                output_project.read_text(encoding="utf-8"))["assets"])
            self.assertEqual(registry.diagnostics(output), [])
            self.assertEqual(registry.binding("sprite", "jeanne")["id"],
                             "jeanne_idle")
            self.assertEqual(registry.binding("animation", "jeanne_move_south")["id"],
                             "anim_jeanne_walk")
            self.assertIsNone(registry.binding("animation", "jeanne_idle_south"))
            self.assertEqual(registry.binding("animation", "jeanne_attack_west")["id"],
                             "anim_jeanne_attack")
            self.assertEqual(registry.require_reference("legacy_jeanne")["id"],
                             "legacy_jeanne")

    def test_missing_original_asset_rejects_preview_without_creating_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack, content, project = prepare(root)
            game = json.loads(project.read_text(encoding="utf-8"))
            game["assets"] = {
                "version": 1,
                "entries": [{"id": "legacy_jeanne", "kind": "sprite",
                             "path": "art/jeanne/missing.png"}],
                "bindings": {},
            }
            project.write_text(json.dumps(game), encoding="utf-8")
            output = root / "preview"
            from sporebound.model import RuleError
            with self.assertRaises(RuleError):
                installer.install(pack, content, project, output)
            self.assertFalse(output.exists())

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
