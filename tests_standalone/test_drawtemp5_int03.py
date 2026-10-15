"""INT-03 negative release tests and 99-image installer smoke (synthetic PNGs)."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from scripts.certify_int03_assets import certify, expected_derived_paths, verify_rights
from scripts.generate_jeanne_motion import TRANSITIONS, DURATIONS
from scripts.install_watercolor_pack import install
from tests_standalone.test_install_watercolor_pack import PNG, prepare

PREFIX = "assets/watercolor/"


def synthetic_99_pack(root: Path, *, approved=True, tamper=False):
    """Synthetic 1px cels verify plumbing, not actual visual production quality."""
    pack, content, project = prepare(root)
    with ZipFile(pack) as archive:
        index = json.loads(archive.read(PREFIX + "index.json"))
        registry = json.loads(archive.read(PREFIX + "registry.json"))
    originals = {row["path"]: sha256(PNG).hexdigest() for row in index["sprites"]}
    for row in index["sprites"]:
        row["frame_size"] = [1, 1]
        row["sheet"] = row["path"].split("/")[1]
    registry["entries"] = [
        row for row in registry["entries"]
        if row["id"] not in ("anim_jeanne_walk", "anim_jeanne_attack")
    ]
    derived = {}
    for action, steps in TRANSITIONS.items():
        frames = []
        for segment, (start, _, count) in enumerate(steps):
            frames.append({"sprite": f"jeanne_{start}",
                           "duration_ms": DURATIONS[action]})
            for subframe in range(1, count + 1):
                aid = f"jeanne_motion_{action}_{segment:02d}_{subframe:02d}"
                rel = f"sprites/jeanne_motion/{action}_{segment:02d}_{subframe:02d}.png"
                derived[rel] = sha256(PNG).hexdigest()
                index["sprites"].append({"id": aid, "kind": "sprite", "path": rel,
                                         "sheet": "jeanne", "frame_size": [1, 1]})
                registry["entries"].append({"id": aid, "kind": "sprite", "path": rel})
                frames.append({"sprite": aid, "duration_ms": DURATIONS[action]})
        if action == "attack":
            frames.append({"sprite": "jeanne_guard",
                           "duration_ms": DURATIONS[action]})
        registry["entries"].append({
            "id": f"anim_jeanne_{action}", "kind": "animation",
            "loop": action == "walk", "frames": frames,
        })
    provenance = {
        "schema_version": 1, "archive_sha256": "a" * 64,
        "sprite_hashes": originals, "derived_hashes": derived,
    }
    rights = {
        "schema_version": 1, "source_archive_sha256": "a" * 64,
        "status": "approved" if approved else "pending",
        "rights_holder": "Test artist", "license_id": "fixture-only",
        "evidence": "test fixture; not a real grant",
        "allow_modification": True, "allow_redistribution": True,
    }
    with ZipFile(pack, "w") as archive:
        for name, obj in (("index.json", index), ("registry.json", registry),
                          ("provenance.json", provenance), ("rights.json", rights)):
            archive.writestr(PREFIX + name, json.dumps(obj))
        for rel in (*originals, *derived):
            bad = tamper and rel == next(iter(derived))
            archive.writestr(PREFIX + rel, b"invalid" if bad else PNG)
    return pack, content, project


class INT03Tests(unittest.TestCase):
    def test_motion_contract_has_exactly_eleven_derivatives(self):
        paths = expected_derived_paths()
        self.assertEqual(len(paths), 11)
        self.assertIn("sprites/jeanne_motion/walk_00_01.png", paths)
        self.assertIn("sprites/jeanne_motion/attack_02_02.png", paths)

    def test_unapproved_and_unproven_rights_fail_closed(self):
        provenance = {"archive_sha256": "a" * 64}
        with self.assertRaisesRegex(ValueError, "rights manifest"):
            verify_rights({}, provenance)
        rights = {
            "schema_version": 1, "source_archive_sha256": "a" * 64,
            "status": "pending", "rights_holder": "Test artist",
            "license_id": "fixture-only", "evidence": "fixture-only",
            "allow_modification": True, "allow_redistribution": True,
        }
        with self.assertRaisesRegex(ValueError, "not been approved"):
            verify_rights(rights, provenance)
        rights["status"] = "approved"
        rights["allow_redistribution"] = False
        with self.assertRaisesRegex(ValueError, "redistribution"):
            verify_rights(rights, provenance)
        rights["allow_redistribution"] = True
        rights["source_archive_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "source archive mismatch"):
            verify_rights(rights, provenance)

    def test_missing_published_pngs_cannot_pass_certification(self):
        with TemporaryDirectory() as temp:
            with self.assertRaises((OSError, ValueError, KeyError)):
                certify(Path(temp))

    def test_installer_resolves_99_published_motion_frames_and_rights(self):
        from sporebound.assets import AssetRegistry
        with TemporaryDirectory() as temp:
            root = Path(temp)
            pack, content, project = synthetic_99_pack(root)
            installed = install(pack, content, project, root / "game")
            game_root = installed.parent
            self.assertEqual(len(list((game_root / PREFIX / "sprites").rglob("*.png"))), 99)
            self.assertTrue((game_root / PREFIX / "rights.json").is_file())
            self.assertTrue((game_root / PREFIX / "provenance.json").is_file())
            registry = AssetRegistry(json.loads(installed.read_text())["assets"])
            self.assertEqual(registry.diagnostics(game_root), [])
            self.assertEqual(registry.binding("animation", "jeanne_move")["id"],
                             "anim_jeanne_walk")
            self.assertEqual(registry.binding("animation", "jeanne_attack_west")["id"],
                             "anim_jeanne_attack")

    def test_unlicensed_99_pack_cannot_create_output(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            pack, content, project = synthetic_99_pack(root, approved=False)
            with self.assertRaisesRegex(ValueError, "rights"):
                install(pack, content, project, root / "game")
            self.assertFalse((root / "game").exists())

    def test_tampered_png_cannot_create_output(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            pack, content, project = synthetic_99_pack(root, tamper=True)
            with self.assertRaisesRegex(ValueError, "PNG"):
                install(pack, content, project, root / "game")
            self.assertFalse((root / "game").exists())


if __name__ == "__main__":
    unittest.main()
