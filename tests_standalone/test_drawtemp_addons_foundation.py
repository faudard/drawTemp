"""Headless contract tests: no PySide6 dependency."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from drawtemp.addons import AddonError, AddonManager, read_addon_manifest, validate_addon_manifest


def sample(name="terrain-kit", *, deps=None, point="studio.tool"):
    permission_sets = {
        "studio.tool": ["project.read", "map.tiles.write"],
        "studio.dock": ["project.read"],
        "game.event": ["events.write"],
    }
    return {
        "schema_version": 3,
        "id": name,
        "name": name,
        "namespace": "org.example." + name.replace("-", ""),
        "version": "1.2.0",
        "kind": "game" if point == "game.event" else "editor",
        "sdk": {"min_api": "1.0.0", "max_api": "2.0.0",
                "required_features": ["addons-foundation.v1"]},
        "capabilities": [point],
        "permissions": permission_sets[point],
        "dependencies": deps or [],
        "contributions": [
            {"id": "main", "point": point,
             "config": {"algorithm": "builtin.autotile-v1"}}
        ],
        "rights": {"license": "MIT", "origin": "Test metadata",
                   "redistributable": True},
    }


def dependency(name, low="1.0.0", high="2.0.0"):
    return {"id": name, "min_version": low, "max_version": high}


class AddonSchemaTests(unittest.TestCase):
    def test_valid_is_detached_and_sdk_feature_exists(self):
        data = sample()
        validated = validate_addon_manifest(data)
        validated["contributions"][0]["config"]["algorithm"] = "changed"
        self.assertEqual(data["contributions"][0]["config"]["algorithm"],
                         "builtin.autotile-v1")
        from drawtemp.sdk import AddonManager as PublicManager, capabilities
        self.assertIs(PublicManager, AddonManager)
        self.assertIn("addons-foundation.v1", capabilities()["features"])

    def test_executable_fields_are_rejected(self):
        for field in ("entrypoint", "python", "script", "qml", "subprocess"):
            with self.subTest(field=field):
                data = sample()
                data["contributions"][0]["config"]["nested"] = {field: "attack"}
                with self.assertRaises(AddonError) as ctx:
                    validate_addon_manifest(data)
                self.assertEqual(ctx.exception.code, "executable_config")
        data = sample()
        data["entrypoint"] = "evil.py"
        with self.assertRaises(AddonError):
            validate_addon_manifest(data)

    def test_permission_and_capability_must_match(self):
        data = sample()
        data["permissions"] = ["project.read"]
        with self.assertRaises(AddonError) as ctx:
            validate_addon_manifest(data)
        self.assertEqual(ctx.exception.code, "invalid_permission")
        data = sample()
        data["capabilities"] = ["studio.tool", "game.event"]
        with self.assertRaises(AddonError):
            validate_addon_manifest(data)
        data = sample()
        data["contributions"][0]["point"] = "game.event"
        with self.assertRaises(AddonError):
            validate_addon_manifest(data)

    def test_version_sdk_and_dependency_validation(self):
        data = sample()
        data["sdk"]["required_features"].append("unknown.v1")
        with self.assertRaises(AddonError) as ctx:
            validate_addon_manifest(data)
        self.assertEqual(ctx.exception.code, "incompatible_sdk")
        data = sample()
        data["version"] = "v1"
        with self.assertRaises(AddonError):
            validate_addon_manifest(data)
        data = sample()
        data["schema_version"] = True
        with self.assertRaises(AddonError):
            validate_addon_manifest(data)
        data = sample(deps=[dependency("terrain-kit")])
        with self.assertRaises(AddonError):
            validate_addon_manifest(data)
        data = sample(deps=[dependency("other-kit", "2.0.0", "1.0.0")])
        with self.assertRaises(AddonError):
            validate_addon_manifest(data)

    def test_file_read_is_strict(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "manifest.json"
            path.write_text('{"id":"a","id":"b"}', encoding="utf-8")
            with self.assertRaises(AddonError) as ctx:
                read_addon_manifest(path)
            self.assertEqual(ctx.exception.code, "duplicate_json_key")
            path.write_text(json.dumps(sample()), encoding="utf-8")
            self.assertEqual(AddonManager().register_file(path)["id"], "terrain-kit")
            link = Path(d) / "link.json"
            try:
                link.symlink_to(path)
            except (OSError, NotImplementedError):
                return
            with self.assertRaises(AddonError) as ctx:
                read_addon_manifest(link)
            self.assertEqual(ctx.exception.code, "unsafe_path")


class AddonManagerTests(unittest.TestCase):
    def test_explicit_consent_disable_and_readonly_snapshots(self):
        manager = AddonManager()
        manager.register(sample())
        self.assertFalse(manager.status("terrain-kit")["enabled"])
        with self.assertRaises(AddonError) as ctx:
            manager.enable("terrain-kit", grants=["project.read"])
        self.assertEqual(ctx.exception.code, "permission_denied")
        manager.enable("terrain-kit", grants=["project.read", "map.tiles.write"])
        self.assertTrue(manager.status("terrain-kit")["enabled"])
        manager.manifest("terrain-kit")["permissions"].clear()
        manager.status("terrain-kit")["required_permissions"].clear()
        self.assertEqual(len(manager.manifest("terrain-kit")["permissions"]), 2)
        manager.disable("terrain-kit")
        self.assertEqual(manager.status("terrain-kit")["grants"], [])
        self.assertFalse(manager.status("terrain-kit")["code_executed"])

    def test_dependency_order_ranges_and_lock(self):
        manager = AddonManager()
        child = sample("terrain-helper", deps=[dependency("terrain-kit")])
        with self.assertRaises(AddonError) as ctx:
            manager.register(child)
        self.assertEqual(ctx.exception.code, "missing_dependency")
        manager.register(sample())
        invalid = sample("bad-helper", deps=[dependency("terrain-kit", "2.0.0", "3.0.0")])
        with self.assertRaises(AddonError) as ctx:
            manager.register(invalid)
        self.assertEqual(ctx.exception.code, "incompatible_dependency")
        manager.register(child)
        with self.assertRaises(AddonError) as ctx:
            manager.enable("terrain-helper", grants=child["permissions"])
        self.assertEqual(ctx.exception.code, "dependency_disabled")
        manager.enable("terrain-kit", grants=sample()["permissions"])
        manager.enable("terrain-helper", grants=child["permissions"])
        lock = copy.deepcopy(manager.lock())
        self.assertTrue(manager.verify_lock(lock))
        with self.assertRaises(AddonError) as ctx:
            manager.disable("terrain-kit")
        self.assertEqual(ctx.exception.code, "required_by")
        with self.assertRaises(AddonError):
            manager.unregister("terrain-kit")
        manager.disable("terrain-helper")
        manager.disable("terrain-kit")
        manager.unregister("terrain-helper")
        manager.unregister("terrain-kit")
        with self.assertRaises(AddonError) as ctx:
            manager.verify_lock(lock)
        self.assertEqual(ctx.exception.code, "lock_mismatch")

    def test_collisions_and_namespace(self):
        manager = AddonManager()
        manager.register(sample())
        with self.assertRaises(AddonError):
            manager.register(sample())
        other = sample("other-kit")
        other["namespace"] = sample()["namespace"]
        with self.assertRaises(AddonError) as ctx:
            manager.register(other)
        self.assertEqual(ctx.exception.code, "collision")

    def test_legacy_manifest_is_inventory_only(self):
        manager = AddonManager()
        legacy = {"api_version": 1, "id": "old-addon", "name": "Old",
                  "capabilities": ["asset-catalog"]}
        state = manager.register(legacy)
        self.assertTrue(state["legacy_read_only"])
        with self.assertRaises(AddonError) as ctx:
            manager.enable("old-addon", grants=[])
        self.assertEqual(ctx.exception.code, "legacy_read_only")

    def test_legacy_r24_and_r47_fixtures(self):
        root = Path(__file__).resolve().parents[1]
        for path, label in [
            ("examples/plugins/quest-helper.json", "r24-v2"),
            ("examples/mods/tool-inspector-r47.json", "r47-mod-v1"),
        ]:
            with self.subTest(path=path):
                state = AddonManager().register_file(root / path)
                self.assertEqual(state["format"], label)
                self.assertTrue(state["legacy_read_only"])
                self.assertFalse(state["enabled"])


if __name__ == "__main__":
    unittest.main()
