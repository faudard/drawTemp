"""R47.F — optional real PlayerController gate for authored modded projects.

Qt-enabled CI only: this proves controller construction, not onscreen GPU,
native Player packaging or release certification.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from drawtemp.export.templates import create_template
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.modding import ModRegistry
from tests_standalone.test_drawtemp_r47c_two_games import setup_registry

try:
    from drawtemp.player.qt_app import build_controller
except ImportError:
    build_controller = None


@unittest.skipUnless(build_controller is not None, "PySide6 Player is unavailable")
class PlayerModPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def build_game(self, name):
        directory = create_template(name, self.root / name)
        session = AuthoringSession.open(directory / "game.json")
        registry, docs, archives, pins = setup_registry(
            self.root / (name + "-packs"))
        for doc in docs:
            registry.enable(doc["id"], grants=doc["permissions"])
            registry.apply_extension(
                doc["id"], session, expected_revision=session.revision)
        session.save()
        return directory, registry, docs, archives, pins

    def test_controller_build_with_explicit_mod_gates_in_two_games(self):
        for game in ("tactical", "asterion"):
            with self.subTest(game=game):
                directory, registry, docs, archives, pins = self.build_game(game)
                controller = build_controller(
                    content_path=directory / "game.json",
                    mod_registry=registry, expected_mod_pins=pins,
                    managed_mod_namespaces=tuple(doc["namespace"] for doc in docs),
                    save_dir=self.root / (game + "-saves"))
                self.assertEqual(controller.project.title,
                                 controller.project.title.strip())
                self.assertEqual(controller.campaign_id,
                                 controller.project.campaigns[0]["id"])
                self.assertFalse(controller.slots())

    def test_corrupt_pack_prevents_controller_instantiation(self):
        directory, registry, docs, archives, pins = self.build_game("tactical")
        archive = next(iter(archives[docs[0]["id"]].values()))
        archive.write_bytes(b"modified since mod authoring")
        with self.assertRaisesRegex(ValueError, "resource_changed"):
            build_controller(
                content_path=directory / "game.json",
                mod_registry=registry, expected_mod_pins=pins,
                managed_mod_namespaces=[doc["namespace"] for doc in docs],
                save_dir=self.root / "saves")
        self.assertFalse((self.root / "saves").exists())

    def test_symlinked_content_is_rejected_before_controller_creation(self):
        directory, registry, docs, archives, pins = self.build_game("tactical")
        link = self.root / "alias.json"
        try:
            link.symlink_to(directory / "game.json")
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation not permitted on this runner")
        with self.assertRaisesRegex(ValueError, "symlinked Content"):
            build_controller(
                content_path=link, mod_registry=registry,
                expected_mod_pins=pins,
                managed_mod_namespaces=[doc["namespace"] for doc in docs],
                save_dir=self.root / "saves")

    def test_incomplete_gate_configuration_refused(self):
        directory, registry, docs, archives, pins = self.build_game("tactical")
        with self.assertRaisesRegex(ValueError, "provided together"):
            build_controller(content_path=directory / "game.json",
                             mod_registry=registry)
        with self.assertRaisesRegex(ValueError, "explicit authored Content"):
            build_controller(reference=True, mod_registry=registry,
                             expected_mod_pins=pins)
        with self.assertRaisesRegex(ValueError, "canonical Content"):
            build_controller(
                content_path=directory / "game.json",
                project_path=directory / "other-project.json",
                mod_registry=registry, expected_mod_pins=pins)


if __name__ == "__main__":
    unittest.main()
