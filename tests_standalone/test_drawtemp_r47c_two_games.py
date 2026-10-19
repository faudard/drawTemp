"""R47.C integration evidence: two inert mods, two games, canonical saves/replays.

These are headless project/export-preflight checks, not executable Player,
Qt onscreen, hardware GPU, human asset approvals or release certification.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import Content, GameProject, GameSession
from drawtemp.export.creator_packs import build_pack, inspect_pack
from drawtemp.export.r15 import preflight
from drawtemp.export.templates import create_template
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.modding import ModError, ModRegistry, read_mod_manifest
from drawtemp.sdk.replay import verify_recording

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = (
    ROOT / "examples/mods/combat-tactics-r47.json",
    ROOT / "examples/mods/tool-inspector-r47.json",
)


def fixture_manifests():
    return [read_mod_manifest(path) for path in FIXTURES]


def self_authored_resource(root, name):
    """Build a real inert R30 pack for pinned-integrity checks."""
    root.mkdir(parents=True, exist_ok=True)
    source = root / (name + "-source")
    source.mkdir()
    payload = json.dumps(
        {"kind": name, "note": "original R47 test-only data"},
        sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    (source / "notes.json").write_bytes(payload)
    manifest = {
        "schema": 1, "id": name, "version": "1.0.0", "kind": "mixed",
        "requires": {"min_api": "1.0.0", "max_api": "2.0.0",
                     "features": ["authoring.v1"]},
        "files": [
            {"path": "notes.json", "size": len(payload),
             "sha256": hashlib.sha256(payload).hexdigest(),
             "license": "CC0-1.0", "origin": "Original R47 test fixture"}
        ],
    }
    path = build_pack(source, root / (name + ".zip"), manifest)
    return path, inspect_pack(path)


def typed_pair(snapshot):
    data = snapshot.to_dict()
    content = Content.from_dict(data["content"])
    project = GameProject.from_dict(data["project"], content)
    return content, project


def setup_registry(root):
    registry = ModRegistry()
    mod_docs = fixture_manifests()
    archives = {}
    for doc in mod_docs:
        archive, inspection = self_authored_resource(root, doc["id"] + "-assets")
        doc["resources"] = [{
            "id": inspection.pack_id, "version": inspection.version,
            "sha256": inspection.archive_sha256
        }]
        archives[doc["id"]] = {inspection.pack_id: archive}
        registry.install(doc, resource_paths=archives[doc["id"]])
    pins = {row["id"]: registry.status(row["id"])["manifest_sha256"]
            for row in mod_docs}
    return registry, mod_docs, archives, pins


class TwoGamesTwoModsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def _apply_pair(self, template):
        project_dir = create_template(template, self.root / template)
        original_content = json.loads((project_dir / "game.json").read_text(encoding="utf-8"))
        session = AuthoringSession.open(project_dir / "game.json")
        registry, docs, archives, pins = setup_registry(self.root / (template + "-packs"))
        # The pack root must be created before build_pack to avoid
        # relying on unspecified filesystem staging.
        for doc in docs:
            state = registry.status(doc["id"])
            self.assertFalse(state["rights_verified"])
            self.assertFalse(state["enabled"])
            with self.assertRaises(ModError):
                registry.preview_extension(doc["id"], session)
            registry.enable(doc["id"], grants=doc["permissions"])
            registry.apply_extension(doc["id"], session,
                                     expected_revision=session.revision)
        report = registry.audit_project(session.snapshot(), expected_pins=pins)
        self.assertTrue(report["compatible"], report["errors"])
        self.assertFalse(report["rights_verified"])
        self.assertFalse(report["native_export_verified"])
        self.assertFalse(report["release_certified"])
        self.assertEqual(set(report["verified_mod_ids"]), set(pins))
        self.assertEqual(original_content, json.loads(
            (project_dir / "game.json").read_text(encoding="utf-8")))
        session.save()
        self.assertEqual(original_content, json.loads(
            (project_dir / "game.json").read_text(encoding="utf-8")))
        self.assertTrue(preflight(project_dir / "game.json")["passed"])

        reopened = AuthoringSession.open(project_dir / "game.json")
        self.assertEqual(
            reopened.snapshot().to_dict()["project"],
            session.snapshot().to_dict()["project"],
        )
        self.assertTrue(registry.audit_project(
            reopened.snapshot(), expected_pins=pins)["compatible"])
        missing = ModRegistry().audit_project(reopened.snapshot(), expected_pins=pins)
        self.assertFalse(missing["compatible"])
        self.assertTrue(all("missing_mod" in err for err in missing["errors"]))
        # The canonical GameSession owns CT, RNG, save/replay; mods remain inert.
        content, game = typed_pair(reopened.snapshot())
        campaign_id = game.campaigns[0]["id"]
        recording = GameSession.new(content, game, campaign_id, seed=2026).recording()
        self.assertEqual(
            verify_recording(recording, content, game).recording(), recording)
        return project_dir, registry, docs, archives, pins, reopened

    def test_two_mods_roundtrip_on_tactical_and_asterion(self):
        for template in ("tactical", "asterion"):
            with self.subTest(game=template):
                game_dir, registry, docs, archives, pins, session = self._apply_pair(template)
                extensions = session.snapshot().to_dict()["project"]["extensions"]
                self.assertIn("org.example.r47.combat", extensions)
                self.assertIn("org.example.r47.inspector", extensions)
                self.assertTrue((game_dir / "game.game.json").is_file())
                # Rejection of downgrade/reinstall never edits project data.
                before = deepcopy(session.snapshot().to_dict())
                changed = deepcopy(docs[0])
                changed["version"] = "0.9.0"
                with self.assertRaises(ModError) as error:
                    registry.install(changed, resource_paths=archives[docs[0]["id"]])
                self.assertEqual(error.exception.code, "collision")
                self.assertEqual(before, session.snapshot().to_dict())
                # Uninstall cannot discard live namespace data.
                for doc in docs:
                    with self.assertRaises(ModError) as error:
                        registry.uninstall(doc["id"], project=session.snapshot())
                    self.assertEqual(error.exception.code, "data_in_use")
                for doc in docs:
                    registry.disable(doc["id"])
                    self.assertEqual(registry.status(doc["id"])["grants"], [])
                self.assertTrue(registry.audit_project(
                    session.snapshot(), expected_pins=pins)["compatible"])

    def test_version_roundtrip_two_games_keeps_replays_and_project_bytes(self):
        for template in ("tactical", "asterion"):
            with self.subTest(game=template):
                game_dir, registry, docs, archives, pins, editor = self._apply_pair(template)
                source = (game_dir / "game.game.json").read_bytes()
                mod_id = docs[0]["id"]
                previous_sha = pins[mod_id]
                newer = deepcopy(docs[0])
                newer["version"] = "1.1.0"
                upgraded = registry.replace_version(
                    mod_id, newer, project=editor.snapshot())
                self.assertEqual(upgraded["version"], "1.1.0")
                self.assertEqual((game_dir / "game.game.json").read_bytes(), source)
                self.assertFalse(registry.status(mod_id)["enabled"])
                stale = registry.audit_project(editor.snapshot(), expected_pins=pins)
                self.assertFalse(stale["compatible"])
                self.assertIn("manifest_changed", stale["errors"][0])
                pins[mod_id] = registry.status(mod_id)["manifest_sha256"]
                self.assertTrue(registry.audit_project(
                    editor.snapshot(), expected_pins=pins)["compatible"])
                reverted = registry.replace_version(
                    mod_id, docs[0], project=editor.snapshot(),
                    allow_downgrade=True)
                self.assertTrue(reverted["downgraded"])
                self.assertEqual(registry.status(mod_id)["manifest_sha256"], previous_sha)
                self.assertEqual((game_dir / "game.game.json").read_bytes(), source)
                content, game = typed_pair(editor.snapshot())
                recording = GameSession.new(
                    content, game, game.campaigns[0]["id"], seed=47).recording()
                self.assertEqual(verify_recording(
                    recording, content, game).recording(), recording)

    def test_pack_changed_after_install_fails_closed_on_audit(self):
        create_template("tactical", self.root / "tactical")
        session = AuthoringSession.open(self.root / "tactical/game.json")
        pack_root = self.root / "pack-root"
        pack_root.mkdir()
        registry, docs, archives, pins = setup_registry(pack_root)
        for doc in docs:
            registry.enable(doc["id"], grants=doc["permissions"])
            registry.apply_extension(doc["id"], session,
                                     expected_revision=session.revision)
        self.assertTrue(registry.audit_project(
            session.snapshot(), expected_pins=pins)["compatible"])
        pack = next(iter(archives[docs[0]["id"]].values()))
        pack.write_bytes(b"corrupted zip after installation")
        diagnostic = registry.audit_project(session.snapshot(), expected_pins=pins)
        self.assertFalse(diagnostic["compatible"])
        self.assertIn(docs[0]["id"] + ": resource_changed", diagnostic["errors"])
        self.assertFalse(diagnostic["release_certified"])

    def test_missing_or_wrong_digest_does_not_delete_user_data(self):
        project_dir = create_template("asterion", self.root / "asterion")
        session = AuthoringSession.open(project_dir / "game.json")
        pack_root = self.root / "pack-root"
        pack_root.mkdir()
        registry, docs, archives, pins = setup_registry(pack_root)
        for doc in docs:
            registry.enable(doc["id"], grants=doc["permissions"])
            registry.apply_extension(doc["id"], session,
                                     expected_revision=session.revision)
        original = session.snapshot().to_dict()
        invalid = deepcopy(pins)
        invalid[docs[0]["id"]] = "0" * 64
        report = registry.audit_project(session.snapshot(), expected_pins=invalid)
        self.assertFalse(report["compatible"])
        self.assertIn("manifest_changed", report["errors"][0])
        tampered = deepcopy(original)
        tampered["project"]["extensions"]["org.example.r47.combat"]["data"]["family"] = "forged"
        diagnostic = registry.audit_project(tampered, expected_pins=pins)
        self.assertFalse(diagnostic["compatible"])
        self.assertIn("namespace_changed", diagnostic["errors"][0])
        self.assertEqual(original, session.snapshot().to_dict())
        with self.assertRaises(ModError):
            registry.audit_project(session.snapshot(), expected_pins={"bad/id": "a" * 64})

    def test_second_pack_must_not_smuggle_executable_code(self):
        pack_root = self.root / "pack-root"
        pack_root.mkdir()
        registry, docs, archives, pins = setup_registry(pack_root)
        rejected = deepcopy(docs[1])
        rejected["id"] = "script-injection"
        rejected["namespace"] = "org.example.r47.script"
        rejected["entrypoint"] = "python:eval"
        with self.assertRaises(ModError):
            registry.install(rejected, resource_paths=archives[docs[1]["id"]])
        self.assertEqual(len(registry.statuses()), 2)


if __name__ == "__main__":
    unittest.main()
