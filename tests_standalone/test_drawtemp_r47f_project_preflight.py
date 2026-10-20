"""R47.F: pre-Player read-only mod audit on canonical two-file projects."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from drawtemp.export.templates import create_template
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.mod_preflight import inspect_modded_project
from drawtemp.sdk.modding import ModError, ModRegistry
from tests_standalone.test_drawtemp_r47c_two_games import setup_registry


class ModdedProjectPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def installed_project(self, template):
        path = create_template(template, self.root / template)
        session = AuthoringSession.open(path / "game.json")
        registry, docs, archives, pins = setup_registry(self.root / (template + "-packs"))
        for doc in docs:
            registry.enable(doc["id"], grants=doc["permissions"])
            registry.apply_extension(doc["id"], session,
                                     expected_revision=session.revision)
        session.save()
        scope = [doc["namespace"] for doc in docs]
        return path, registry, docs, archives, pins, scope

    def test_tactical_and_asterion_roundtrip_preplayer_without_writes(self):
        for template in ("tactical", "asterion"):
            with self.subTest(game=template):
                directory, registry, docs, archives, pins, scope = (
                    self.installed_project(template))
                content_path = directory / "game.json"
                game_path = directory / "game.game.json"
                before = (content_path.read_bytes(), game_path.read_bytes())
                result = inspect_modded_project(
                    content_path, registry, expected_pins=pins,
                    managed_namespaces=scope)
                self.assertTrue(result["ready_for_player_preview"], result["errors"])
                self.assertTrue(result["r15_passed"])
                self.assertEqual(set(result["mod_audit"]["verified_mod_ids"]),
                                 set(pins))
                self.assertFalse(result["rights_verified"])
                self.assertFalse(result["release_certified"])
                self.assertFalse(result["native_player_verified"])
                self.assertEqual(before, (content_path.read_bytes(),
                                          game_path.read_bytes()))
                # Asterion owns a pre-existing Core namespace. It is not
                # automatically accused of being an untrusted mod.
                if template == "asterion":
                    self.assertIn("org.drawtemp.example.asterion",
                                  json.loads(game_path.read_text())["extensions"])

    def test_missing_mod_and_orphan_namespace_fail_without_data_loss(self):
        directory, registry, docs, archives, pins, scope = (
            self.installed_project("asterion"))
        source = directory / "game.json"
        original = (source.read_bytes(), (directory / "game.game.json").read_bytes())
        report = inspect_modded_project(
            source, ModRegistry(), expected_pins=pins,
            managed_namespaces=scope)
        self.assertFalse(report["ready_for_player_preview"])
        self.assertIn("missing_mod", " ".join(report["errors"]))
        self.assertIn("orphan_namespace", " ".join(report["errors"]))
        self.assertEqual(original, (source.read_bytes(),
                                    (directory / "game.game.json").read_bytes()))

    def test_unpinned_installed_mod_is_not_ignored(self):
        directory, registry, docs, archives, pins, scope = (
            self.installed_project("tactical"))
        pins.pop(docs[1]["id"])
        report = inspect_modded_project(
            directory / "game.json", registry, expected_pins=pins,
            managed_namespaces=scope)
        self.assertFalse(report["ready_for_player_preview"])
        self.assertIn("unpinned_mod", " ".join(report["errors"]))
        self.assertIn("orphan_namespace", " ".join(report["errors"]))

    def test_modified_r30_pack_blocks_player_preview(self):
        directory, registry, docs, archives, pins, scope = (
            self.installed_project("tactical"))
        asset = next(iter(archives[docs[0]["id"]].values()))
        asset.write_bytes(b"mod archive replaced on disk")
        report = inspect_modded_project(
            directory / "game.json", registry, expected_pins=pins,
            managed_namespaces=scope)
        self.assertFalse(report["ready_for_player_preview"])
        self.assertIn("resource_changed", " ".join(report["errors"]))

    def test_duplicate_json_keys_and_invalid_paths_fail_closed(self):
        directory, registry, docs, archives, pins, scope = (
            self.installed_project("tactical"))
        source = directory / "game.json"
        game = directory / "game.game.json"
        game.write_text('{"version": 1, "version": 1}', encoding="utf-8")
        report = inspect_modded_project(
            source, registry, expected_pins=pins, managed_namespaces=scope)
        self.assertFalse(report["ready_for_player_preview"])
        self.assertIn("Duplicate JSON key", " ".join(report["errors"]))
        source.unlink()
        absent = inspect_modded_project(
            source, registry, expected_pins=pins, managed_namespaces=scope)
        self.assertFalse(absent["ready_for_player_preview"])
        self.assertIn("invalid_project_files", " ".join(absent["errors"]))

    def test_detects_content_swap_during_asset_preflight(self):
        directory, registry, docs, archives, pins, scope = (
            self.installed_project("tactical"))
        source = directory / "game.json"
        game = directory / "game.game.json"
        from drawtemp.export.r15 import preflight as canonical_preflight

        def changed_during_scan(path):
            output = canonical_preflight(path)
            game.write_bytes(game.read_bytes() + b" ")
            return output

        with patch("drawtemp.sdk.mod_preflight.preflight",
                   side_effect=changed_during_scan):
            report = inspect_modded_project(
                source, registry, expected_pins=pins, managed_namespaces=scope)
        self.assertFalse(report["ready_for_player_preview"])
        self.assertIn("changed_during_preflight", report["errors"])

    def test_invalid_pins_and_scope_are_caller_errors(self):
        directory, registry, docs, archives, pins, scope = (
            self.installed_project("tactical"))
        with self.assertRaises(ModError) as bad:
            inspect_modded_project(
                directory / "game.json", registry,
                expected_pins={"invalid/path": "0" * 64})
        self.assertEqual(bad.exception.code, "invalid_pins")
        with self.assertRaises(ModError) as bad:
            inspect_modded_project(
                directory / "game.json", registry, expected_pins=pins,
                managed_namespaces=["invalid/namespace"])
        self.assertEqual(bad.exception.code, "invalid_namespaces")


if __name__ == "__main__":
    unittest.main()
