"""Repository hygiene: the standalone runtime must not regress to Godot artifacts."""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_SUFFIXES = {".gd", ".uid", ".tscn", ".tres", ".gdshader", ".import", ".godot"}
OBSOLETE_ROOTS = (
    "addons/sporebound_studio",
    "legacy_sources",
    ".sporebound_patch_backup",
)
IGNORED_UNTRACKED = {".git", ".venv", "__pycache__", "build", "dist", "saves"}


def source_paths():
    """Use tracked files when Git exists, avoiding false positives from local caches."""
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        capture_output=True,
        check=False,
    ) if shutil_which_git() else None
    if result is not None and result.returncode == 0:
        return [ROOT / name.decode("utf-8") for name in result.stdout.split(b"\0") if name]
    paths = []
    for top in ROOT.iterdir():
        if top.name in IGNORED_UNTRACKED:
            continue
        if top.is_file():
            paths.append(top)
        elif top.is_dir():
            paths.extend(p for p in top.rglob("*") if p.is_file()
                         and not set(p.relative_to(ROOT).parts) & IGNORED_UNTRACKED)
    return paths


def shutil_which_git():
    from shutil import which
    return which("git") is not None


class StandaloneRepositoryLayoutTests(unittest.TestCase):
    def test_no_tracked_godot_artifacts(self):
        forbidden = sorted(
            str(path.relative_to(ROOT)) for path in source_paths()
            if path.suffix.lower() in FORBIDDEN_SUFFIXES or path.name == "project.godot"
        )
        self.assertEqual([], forbidden, "Remove obsolete Godot files from the active tree")

    def test_no_old_godot_source_directories(self):
        for name in OBSOLETE_ROOTS:
            with self.subTest(path=name):
                self.assertFalse((ROOT / name).exists())

    def test_art_catalog_uses_relative_paths(self):
        catalog = (ROOT / "assets" / "catalog.json").read_text(encoding="utf-8")
        self.assertNotIn("res://", catalog)
        parsed = json.loads(catalog)
        self.assertEqual(parsed["schema_version"], 1)
        self.assertIn("character_portraits", parsed)


if __name__ == "__main__":
    unittest.main()
