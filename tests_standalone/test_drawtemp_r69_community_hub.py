"""R69.A–C: three original inert packs, offline exchange and fail-closed gates."""
from __future__ import annotations

import contextlib
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
import zlib

from drawtemp.export.community_hub_cli import main as community_main
from drawtemp.export.creator_packs import PackError, build_pack, inspect_pack
from drawtemp.export.pack_import import import_pack_to_copy, preview_pack_import
from drawtemp.export.r15 import preflight
from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.community_hub import (
    HubError, acquire_pack, available_updates, publish_pack, read_catalog,
    search_catalog, withdraw_pack,
)
from drawtemp.sdk.reference import reference_project


def tiny_original_png(red):
    """Original synthetic 1x1 pixel for the headless exchange gate."""
    def chunk(name, payload):
        return (struct.pack(">I", len(payload)) + name + payload +
                struct.pack(">I", zlib.crc32(name + payload) & 0xffffffff))
    return (b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(bytes([0, red, 30, 40, 255]))) +
            chunk(b"IEND", b""))


class CommunityHubTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.hub = self.root / "local-hub"
        self.recipient = self.root / "other-creator"
        self.recipient.mkdir()
        self.packs = {}
        for index, (pack_id, kind) in enumerate((
                ("terrain-share", "terrain"),
                ("enemy-share", "enemy"),
                ("hud-share", "hud"))):
            self.packs[pack_id] = self._pack(pack_id, kind, "1.0.0", 70 + index)
        self.source = self.root / "project"
        self.source.mkdir()
        AuthoringSession.new(*reference_project()).save_as(self.source / "game.json")

    def _pack(self, pack_id, kind, version, red):
        folder = self.root / (pack_id + "-" + version)
        (folder / "art").mkdir(parents=True)
        payload = tiny_original_png(red)
        (folder / "art" / "sample.png").write_bytes(payload)
        manifest = {
            "schema": 1, "id": pack_id, "version": version, "kind": kind,
            "requires": {"min_api": "1.0.0", "max_api": "2.0.0",
                         "features": ["authoring.v1"]},
            "files": [{
                "path": "art/sample.png", "sha256": sha256(payload).hexdigest(),
                "size": len(payload), "license": "CC0-1.0",
                "origin": "Original synthetic R69 test pixel: " + pack_id,
            }],
        }
        return build_pack(folder, self.root / (pack_id + "-" + version + ".zip"),
                          manifest)

    def _publish(self, pack_id, path=None):
        return publish_pack(
            self.hub, path or self.packs[pack_id], publisher="r69-test-author",
            declaration="I authored these synthetic pixels and permit sharing.",
            confirm=True,
        )

    def _reject(self, code, fn, *args, **kwargs):
        with self.assertRaises(HubError) as caught:
            fn(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_three_pack_exchange_to_canonical_project_copy_and_withdrawal(self):
        for pack_id in self.packs:
            row = self._publish(pack_id)
            self.assertEqual(row["status"], "available")
            self.assertFalse(row["legal_clearance"])
        self.assertEqual(len(search_catalog(self.hub)), 3)
        for pack_id in self.packs:
            saved = self.recipient / (pack_id + ".zip")
            result = acquire_pack(self.hub, pack_id, "1.0.0", saved,
                                  expected_sha256=read_catalog(self.hub)["packs"][
                                      sorted(self.packs).index(pack_id)]["sha256"],
                                  confirm=True)
            self.assertFalse(result["project_modified"])
            self.assertFalse(result["rights_verified"])
            self.assertEqual(inspect_pack(saved).pack_id, pack_id)
            choices = [{"path": "art/sample.png", "kind": "sprite", "name": "sample"}]
            plan = preview_pack_import(self.source / "game.json", saved, choices)
            dest = self.recipient / (pack_id + "-game")
            import_pack_to_copy(plan, dest)
            self.assertTrue(preflight(dest / "game.json")["passed"])
            project = json.loads((dest / "game.game.json").read_text("utf-8"))
            self.assertIn(pack_id + ".sample",
                          {row["id"] for row in project["assets"]["entries"]})
        first = self.recipient / "terrain-share.zip"
        first_bytes = first.read_bytes()
        withdrawn = withdraw_pack(self.hub, "terrain-share", "1.0.0",
                                  reason="Publisher-initiated removal", confirm=True)
        self.assertEqual(withdrawn["status"], "withdrawn")
        self.assertEqual(len(search_catalog(self.hub)), 2)
        self.assertEqual(len(search_catalog(self.hub, include_withdrawn=True)), 3)
        self._reject("withdrawn", acquire_pack, self.hub, "terrain-share", "1.0.0",
                     self.recipient / "again.zip", confirm=True)
        self._reject("immutable_release", self._publish, "terrain-share")
        self.assertEqual(first.read_bytes(), first_bytes)
        self.assertTrue((self.recipient / "terrain-share-game/game.json").exists())
        self.assertTrue((self.hub / "packs" /
                        (withdrawn["sha256"] + ".zip")).is_file())
        # No change whatsoever to the existing canonical project.
        self.assertTrue(preflight(self.source / "game.json")["passed"])

    def test_permissions_versions_and_manual_updates(self):
        self._reject("consent_required", publish_pack, self.hub,
                     self.packs["terrain-share"], publisher="r69-test-author",
                     declaration="These test pixels are my own.")
        self.assertFalse(self.hub.exists())
        base = self._publish("terrain-share")
        self._reject("immutable_release", self._publish, "terrain-share")
        old = self._pack("terrain-share", "terrain", "0.9.0", 52)
        self._reject("non_monotonic_version", self._publish, "terrain-share", old)
        newer = self._pack("terrain-share", "terrain", "1.1.0", 95)
        self._publish("terrain-share", newer)
        updates = available_updates(self.hub, {"terrain-share": "1.0.0"})
        self.assertEqual([(r["id"], r["version"]) for r in updates],
                         [("terrain-share", "1.1.0")])
        self.assertEqual(available_updates(self.hub, {"terrain-share": "1.1.0"}), ())
        self._reject("consent_required", acquire_pack, self.hub,
                     "terrain-share", "1.0.0", self.recipient / "not-created.zip")
        self._reject("untrusted_digest", acquire_pack, self.hub,
                     "terrain-share", "1.0.0", self.recipient / "nope.zip",
                     expected_sha256="0" * 64, confirm=True)
        self.assertFalse(list(self.recipient.glob("*.zip")))
        self._reject("consent_required", withdraw_pack, self.hub,
                     "terrain-share", "1.0.0", reason="Author withdrawal")
        self.assertEqual(read_catalog(self.hub)["packs"][0]["sha256"],
                         base["sha256"])

    def test_tamper_fail_closed_and_keep_destination_bytes(self):
        entry = self._publish("enemy-share")
        stored = self.hub / "packs" / (entry["sha256"] + ".zip")
        stored.write_bytes(stored.read_bytes() + b"tamper")
        self._reject("stored_pack_changed", acquire_pack, self.hub, "enemy-share",
                     "1.0.0", self.recipient / "bad.zip", confirm=True)
        self.assertFalse((self.recipient / "bad.zip").exists())
        # Read-only discovery does not trust or scan the blob directory.
        self.assertEqual(len(search_catalog(self.hub)), 1)
        self._reject("stored_pack_changed", self._publish,
                     "enemy-share", self.packs["enemy-share"])
        already = self.recipient / "owned.zip"
        already.write_bytes(b"precious")
        self._reject("stored_pack_changed", acquire_pack, self.hub, "enemy-share",
                     "1.0.0", already, confirm=True)
        self.assertEqual(already.read_bytes(), b"precious")

    def test_reject_duplicate_keys_unknown_fields_and_catalogue_symlinks(self):
        self.hub.mkdir()
        file = self.hub / "catalog.json"
        for content in (
                '{"schema":1,"schema":1,"packs":[]}',
                '{"schema":1,"packs":[],"execute":"evil.py"}',
                '{"schema":1,"packs":[],"x":NaN}',
                "x" * (1024 * 1024 + 1),
        ):
            file.write_text(content, encoding="utf-8")
            with self.assertRaises(HubError):
                read_catalog(self.hub)
        file.unlink()
        try:
            file.symlink_to(self.root / "outside.json")
        except (OSError, NotImplementedError):
            pass
        else:
            self._reject("unsafe_path", read_catalog, self.hub)
            file.unlink()
        entry = self._publish("hud-share")
        blob = self.hub / "packs" / (entry["sha256"] + ".zip")
        blob.unlink()
        try:
            blob.symlink_to(self.packs["hud-share"])
        except (OSError, NotImplementedError):
            pass
        else:
            self._reject("unsafe_path", acquire_pack, self.hub, "hud-share",
                         "1.0.0", self.recipient / "symlink.zip", confirm=True)

    def test_inert_executable_rejection_and_cli_local_discovery(self):
        bad_manifest = {
            "schema": 1, "id": "script-share", "version": "1.0.0",
            "kind": "mixed", "requires": {"min_api": "1.0.0", "max_api": "2.0.0",
                                        "features": ["authoring.v1"]},
            "files": [{"path": "run.py", "size": 0, "sha256": sha256(b"").hexdigest(),
                       "license": "MIT", "origin": "Unknown code"}],
        }
        with self.assertRaises(PackError):
            build_pack(self.root, self.root / "bad-code.zip", bad_manifest)
        archive = self.packs["hud-share"]
        out = StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(community_main([
                "publish", "--catalog", str(self.hub), "--pack", str(archive),
                "--publisher", "r69-test-author",
                "--declaration", "I authored these synthetic test assets.",
                "--confirm",
            ]), 0)
        self.assertTrue(json.loads(out.getvalue())["ok"])
        out = StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(community_main([
                "search", "--catalog", str(self.hub), "--query", "hud",
            ]), 0)
        self.assertEqual(len(json.loads(out.getvalue())["result"]), 1)
        out = StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(community_main([
                "updates", "--catalog", str(self.hub),
                "--installed", str(self._installed_file()),
            ]), 0)
        self.assertEqual(json.loads(out.getvalue())["result"], [])

    def _installed_file(self):
        path = self.root / "installed.json"
        path.write_text(json.dumps({"hud-share": "1.0.0"}), encoding="utf-8")
        return path


if __name__ == "__main__":
    unittest.main()
