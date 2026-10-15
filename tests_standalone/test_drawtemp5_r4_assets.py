"""R4 asset authoring, directory safety, render contracts and deterministic art."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

from drawtemp.assets.atlas import (
    DirectionalLayout, load_annotations, license_issues,
    plan_directional_import, plan_strip_import, png_dimensions, save_annotations,
)
from drawtemp.assets.catalog import (
    AssetIndex, BrowserPreferences, plan_legacy_migration,
)
from drawtemp.assets.resolver import AssetResolver
from drawtemp.assets.terrain import (
    animated_environment_assets, environment_preview, material_at, map_material,
)
from sporebound.assets import AssetRegistry
from sporebound.model import RuleError


def png_chunk(kind, payload):
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))


def rgba_png(w, h):
    raw = (b"\x00" + b"\x80\x20\x10\xff" * w) * h
    return (b"\x89PNG\r\n\x1a\n"
            + png_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + png_chunk(b"IDAT", zlib.compress(raw))
            + png_chunk(b"IEND", b""))


def jeanne():
    return DirectionalLayout(
        frame_size=(64, 64),
        action_rows={"idle": (0, 1), "move": (2, 3), "attack": (4, 5),
                     "hit": (6,), "defeat": (7,)},
        pivot=(32, 60), footprint=(1, 1), frame_ms=120)


class R4AtlasTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.source = self.root / "jeanne-original.png"
        self.source.write_bytes(rgba_png(256, 512))
        self.empty = AssetRegistry()

    def make_plan(self):
        return plan_directional_import(self.empty, self.source, "jeanne", jeanne())

    def test_import_exact_frames_poses_directions_and_legacy_v1(self):
        plan = self.make_plan()
        registry = AssetRegistry(plan.manifest)
        self.assertEqual(len(plan.manifest["entries"]), 52)
        self.assertEqual(len(plan.annotations), 32)
        for direction in ("south", "east", "north", "west"):
            for pose in ("idle", "move", "attack", "hit", "defeat"):
                anim = registry.require_reference(f"jeanne.{direction}.{pose}", "animation")
                self.assertEqual(len(anim["frames"]), 1 if pose in ("hit", "defeat") else 2)
        self.assertEqual(registry.require_reference("jeanne.east.attack.1")["region"],
                         [64, 320, 64, 64])
        self.assertEqual(plan.manifest["version"], 1)
        self.assertEqual(plan.manifest["bindings"], {})

    def test_copy_resolve_animated_pivot_and_reload(self):
        plan = self.make_plan()
        original_bytes = self.source.read_bytes()
        target = plan.copy_into(self.root)
        self.assertEqual(target.read_bytes(), original_bytes)
        registry = AssetRegistry(plan.manifest)
        self.assertEqual(registry.diagnostics(self.root), [])
        payload = {"version": 1, "sprites": plan.annotations}
        annotation_path = self.root / ".drawtemp" / "r4-annotations.json"
        save_annotations(annotation_path, registry, payload)
        self.assertEqual(load_annotations(annotation_path, registry), payload)
        resolver = AssetResolver(registry, self.root, load_annotations(annotation_path, registry))
        first = resolver.resolve("jeanne.south.move", elapsed_ms=0)
        second = resolver.resolve("jeanne.south.move", elapsed_ms=120)
        looped = resolver.resolve("jeanne.south.move", elapsed_ms=240)
        self.assertEqual(first.asset_id, "jeanne.south.move.0")
        self.assertEqual(second.asset_id, "jeanne.south.move.1")
        self.assertEqual(first, looped)
        self.assertEqual((first.pivot, first.footprint), ((32, 60), (1, 1)))
        self.assertEqual(first.region, (0, 128, 64, 64))
        self.assertEqual(resolver.resolve("jeanne.north.attack", elapsed_ms=9999).asset_id,
                         "jeanne.north.attack.1")
        with self.assertRaises(FileExistsError):
            plan.copy_into(self.root)

    def test_previews_are_pure_and_canonical_assets_grouped(self):
        plan = self.make_plan()
        registry = AssetRegistry(plan.manifest)
        browser = AssetIndex(registry)
        self.assertEqual(len(browser.cards), 20)
        self.assertEqual(len(browser.find("JEANNE", "characters")), 20)
        self.assertEqual(len(browser.find("attaque")), 0)
        self.assertEqual(len(browser.find("attack", "characters")), 4)
        self.assertEqual(len(browser.frames("jeanne.south.attack")), 2)
        self.assertEqual(len(registry.to_dict()["entries"]), 52)

    def test_crc_dimensions_missing_chunks_limits_and_bad_layout(self):
        original = self.source.read_bytes()
        self.assertEqual(png_dimensions(original), (256, 512))
        invalid = [
            original[:-5],
            original.replace(b"IHDR", b"XHDR", 1),
            original[:35] + bytes([original[35] ^ 1]) + original[36:],
            original + b"trailing",
            b"not a png",
        ]
        for contents in invalid:
            with self.subTest(contents=contents[:12]), self.assertRaises(ValueError):
                png_dimensions(contents)
        wrong = DirectionalLayout((32, 32), {"idle": (0,)})
        with self.assertRaises(ValueError):
            plan_directional_import(self.empty, self.source, "jeanne", wrong)
        with self.assertRaises(ValueError):
            plan_directional_import(self.empty, self.source, "../escape", jeanne())
        bad = DirectionalLayout((64, 64), {"idle": (0, 0)})
        with self.assertRaises(ValueError):
            plan_directional_import(self.empty, self.source, "jeanne", bad)

    def test_collisions_digest_change_and_symlink_escape(self):
        plan = self.make_plan()
        with self.assertRaises(RuleError):
            plan_directional_import(AssetRegistry(plan.manifest), self.source,
                                    "JEANNE", jeanne())
        self.source.write_bytes(rgba_png(256, 512)[:-1])
        with self.assertRaises(ValueError):
            plan.copy_into(self.root)
        self.source.write_bytes(rgba_png(256, 512))
        assets = self.root / "assets"
        assets.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory() as external:
            try:
                (assets / "imported").symlink_to(Path(external), target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unavailable")
            with self.assertRaises(ValueError):
                plan.copy_into(self.root)

    def test_annotation_provenance_gate_rejects_forged_metadata(self):
        plan = self.make_plan()
        registry = AssetRegistry(plan.manifest)
        payload = {"version": 1, "sprites": deepcopy(plan.annotations)}
        self.assertEqual(len(license_issues(registry, payload)), 32)
        for item in payload["sprites"].values():
            item["license"] = "CC-BY-4.0"
        self.assertEqual(license_issues(registry, payload), [])
        first = next(iter(payload["sprites"]))
        payload["sprites"][first]["pivot"] = [500, 1]
        with self.assertRaises(ValueError):
            save_annotations(self.root / "bad.json", registry, payload)
        self.assertFalse((self.root / "bad.json").exists())

    def test_horizontal_environment_strip_and_material_repeatability(self):
        data = environment_preview("grass")
        self.assertEqual(png_dimensions(data), (512, 64))
        strip = self.root / "grass.png"
        strip.write_bytes(data)
        p = plan_strip_import(self.empty, strip, "environment.grass",
                              frame_size=(64, 64), count=8, pivot=(32, 54))
        registry = AssetRegistry(p.manifest)
        p.copy_into(self.root)
        self.assertEqual(registry.diagnostics(self.root), [])
        self.assertEqual(len(AssetIndex(registry).cards), 1)
        self.assertEqual(len(AssetResolver(registry, self.root).frames("environment.grass")), 8)
        self.assertEqual(len(animated_environment_assets()), 4)
        same = material_at(13, -3, seed=42, style="bocage")
        self.assertEqual(same, material_at(13, -3, seed=42, style="bocage"))
        class Tile:
            surface = "grass"
            height = 0
        class Board:
            def contains(self, cell):
                return cell in ((0, 0), (1, 0))
            def tile(self, cell):
                return Tile()
        self.assertEqual(map_material(Board(), 0, 0).name, "grass")
        self.assertEqual(map_material(Board(), 0, 0).edges, ())
        with self.assertRaises(ValueError):
            map_material(Board(), 300, 0)

    def test_browser_bookmarks_reload_and_non_destructive_legacy_migration(self):
        path = self.root / ".drawtemp" / "browser.json"
        prefs = BrowserPreferences.load(path)
        prefs.visit("jeanne.south.idle")
        prefs.favorite("jeanne.south.idle")
        self.assertEqual(BrowserPreferences.load(path).recents, ["jeanne.south.idle"])
        self.assertEqual(len(AssetIndex(AssetRegistry(self.make_plan().manifest)).find(
            family="favorites", favorites=prefs.favorites)), 1)
        registry = plan_legacy_migration(self.empty, [
            {"id": "historic_jeanne", "kind": "sprite", "path": "art/old.png"}])
        self.assertEqual(registry.require_reference("historic_jeanne")["path"], "art/old.png")
        with self.assertRaises(RuleError):
            plan_legacy_migration(registry, [
                {"id": "HISTORIC_JEANNE", "kind": "sprite", "path": "art/new.png"}])

    def test_save_reopen_same_registry_and_texture_ids(self):
        from drawtemp.sdk.reference import reference_project
        from drawtemp.assets.project import import_into_project, validate_project_assets
        from sporebound.game_project import GameProject

        content, project = reference_project()
        project_path = self.root / "game.json"
        project.save(project_path, content)
        original = project_path.read_bytes()
        plan = plan_directional_import(
            project.asset_registry(), self.source, "jeanne", jeanne(),
            license_id="CC0-1.0", binding_prefix="jeanne")
        imported = import_into_project(project_path, content, plan)
        reopened = GameProject.load(project_path, content)
        self.assertEqual(imported.to_dict(), reopened.to_dict())
        self.assertNotEqual(original, project_path.read_bytes())
        self.assertEqual(reopened.asset_registry().to_dict(), plan.manifest)
        self.assertEqual(reopened.asset_registry().binding("animation", "jeanne_south_idle")["id"],
                         "jeanne.south.idle")
        self.assertEqual(validate_project_assets(project_path, content), [])
        image = AssetResolver(reopened.asset_registry(), self.root).resolve(
            "jeanne.south.idle", elapsed_ms=121)
        self.assertEqual(image.asset_id, "jeanne.south.idle.1")

    def test_headless_import_path_does_not_load_ui(self):
        program = '''
import sys
class RejectUI:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ("tkinter", "PySide6", "PyQt6"):
            raise AssertionError(fullname)
sys.meta_path.insert(0, RejectUI())
from drawtemp.assets import AssetIndex, DirectionalLayout, AssetResolver
from drawtemp.assets.terrain import material_at, environment_preview
assert material_at(1,2,seed=3).name
assert environment_preview("grass").startswith(b"\\x89PNG")
'''
        subprocess.run([sys.executable, "-c", program],
                       cwd=Path(__file__).resolve().parents[1],
                       check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
