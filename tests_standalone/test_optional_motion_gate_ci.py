"""Dev CI's optional-art split must fail closed on partial publication."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from sporebound.watercolor_catalog import DEFAULT_WATERCOLOR_ROOT
from tests_standalone.watercolor_motion_fixture import motion_publication_claimed
from scripts.certify_int03_assets import certify


class OptionalMotionGateTests(unittest.TestCase):
    def fixtures(self, destination):
        destination = Path(destination)
        for name in ("index.json", "provenance.json", "registry.json"):
            (destination / name).write_bytes(
                (DEFAULT_WATERCOLOR_ROOT / name).read_bytes())
        return destination

    def test_unpublished_source_pack_is_not_claimed_as_production(self):
        with TemporaryDirectory() as directory:
            root = self.fixtures(directory)
            self.assertFalse(motion_publication_claimed(root))
            with self.assertRaises((OSError, ValueError, KeyError)):
                certify(root)  # Strict INT-03 release validation stays closed.

    def test_even_one_unverified_png_triggers_all_release_assertions(self):
        with TemporaryDirectory() as directory:
            root = self.fixtures(directory)
            sprite = root / "sprites" / "jeanne_motion" / "walk_00_01.png"
            sprite.parent.mkdir(parents=True)
            sprite.write_bytes(b"not a real PNG")
            self.assertTrue(motion_publication_claimed(root))
            with self.assertRaises((OSError, ValueError, KeyError)):
                certify(root)

    def test_metadata_only_partial_publication_is_not_skipped(self):
        with TemporaryDirectory() as directory:
            root = self.fixtures(directory)
            prov = root / "provenance.json"
            data = json.loads(prov.read_text(encoding="utf-8"))
            data["derived_hashes"] = {}
            prov.write_text(json.dumps(data), encoding="utf-8")
            self.assertTrue(motion_publication_claimed(root))
            with self.assertRaises((OSError, ValueError, KeyError)):
                certify(root)

    def test_extended_registry_without_pngs_is_not_skipped(self):
        with TemporaryDirectory() as directory:
            root = self.fixtures(directory)
            registry = root / "registry.json"
            data = json.loads(registry.read_text(encoding="utf-8"))
            row = next(item for item in data["entries"]
                       if item["id"] == "anim_jeanne_walk")
            row["frames"].append(row["frames"][-1].copy())
            registry.write_text(json.dumps(data), encoding="utf-8")
            self.assertTrue(motion_publication_claimed(root))


if __name__ == "__main__":
    unittest.main()
