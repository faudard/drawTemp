"""R24.G: canonical semantic diff, conflict detection and one-undo merges."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk import (
    AuthoringError, AuthoringSession, SDK_FEATURES,
    SemanticMergeError, semantic_diff, preview_three_way,
    preview_merge, apply_merge, read_pair,
)
from drawtemp.sdk.reference import reference_project


ROOT = Path(__file__).resolve().parents[1]


def documents():
    content, project = reference_project()
    return {"content": content.to_dict(), "project": project.to_dict()}


def edit_title(document, title):
    result = deepcopy(document)
    result["project"]["title"] = title
    return result


def extension(value):
    return {"schema_version": 1, "data": {"value": value}, "references": []}


def save_pair(pair, content_path):
    session = AuthoringSession.new(pair["content"], pair["project"])
    session.save_as(content_path)
    return content_path


class SemanticDiffTests(unittest.TestCase):
    def test_headless_sdk_contract_and_nested_entity_paths(self):
        self.assertIn("semantic-vcs.v1", SDK_FEATURES)
        base = documents()
        other = deepcopy(base)
        mission = other["content"]["missions"][0]
        mission["name"] = "Nouvelle carte"
        unit = mission["units"][0]
        unit["name"] = "Nouveau héros"
        scene = other["project"]["story"]["scenes"][0]
        scene["text"] = "Nouvelle narration"
        report = semantic_diff(base, other)
        self.assertEqual(report["kind"], "r24g-semantic-diff")
        self.assertEqual(report["schema"], 1)
        self.assertEqual(report["count"], 3)
        changes = report["changes"]
        paths = {row["path"] for row in changes}
        self.assertIn("/content/missions[id=r0_village_forest]/name", paths)
        self.assertIn("/content/missions[id=r0_village_forest]/units[id=" +
                      unit["id"] + "]/name", paths)
        self.assertIn("/project/story/scenes[id=arrival]/text", paths)
        self.assertTrue(all(len(row["before_sha256"]) == 64 for row in changes))
        self.assertEqual(semantic_diff(base, base)["count"], 0)
        self.assertEqual(documents(), base)

    def test_independent_changes_same_entity_and_across_documents(self):
        base = documents()
        ours = deepcopy(base)
        theirs = deepcopy(base)
        ours["content"]["missions"][0]["name"] = "La forêt locale"
        ours["project"]["title"] = "Titre local"
        theirs["content"]["missions"][0]["units"][0]["name"] = "Nom distant"
        theirs["project"]["subtitle"] = "Sous-titre distant"
        review = preview_three_way(base, ours, theirs)
        self.assertTrue(review["can_merge"], review["conflicts"])
        self.assertEqual(review["conflicts"], [])
        merged = review["merged"]
        self.assertEqual(merged["content"]["missions"][0]["name"], "La forêt locale")
        self.assertEqual(merged["content"]["missions"][0]["units"][0]["name"], "Nom distant")
        self.assertEqual(merged["project"]["title"], "Titre local")
        self.assertEqual(merged["project"]["subtitle"], "Sous-titre distant")
        self.assertEqual(ours["project"]["subtitle"], base["project"]["subtitle"])
        self.assertEqual(theirs["project"]["title"], base["project"]["title"])

    def test_disjoint_extensions_can_be_combined_but_same_key_refused(self):
        base = documents()
        ours = deepcopy(base)
        theirs = deepcopy(base)
        ours["project"]["extensions"] = {"org.example.one": extension(1)}
        theirs["project"]["extensions"] = {"org.example.two": extension(2)}
        review = preview_three_way(base, ours, theirs)
        self.assertTrue(review["can_merge"], review["conflicts"])
        extensions = review["merged"]["project"]["extensions"]
        self.assertEqual(set(extensions), {"org.example.one", "org.example.two"})
        other = deepcopy(theirs)
        other["project"]["extensions"] = {"org.example.one": extension(99)}
        conflict = preview_three_way(base, ours, other)
        self.assertFalse(conflict["can_merge"])
        self.assertIsNone(conflict["merged"])
        self.assertTrue(any(row["reason"] == "concurrent_add" and
                            row["path"] == "/project/extensions/org.example.one"
                            for row in conflict["conflicts"]))

    def test_conflicting_edits_have_paths_and_no_hidden_result(self):
        base = documents()
        ours = edit_title(base, "Branche A")
        theirs = edit_title(base, "Branche B")
        review = preview_three_way(base, ours, theirs)
        self.assertFalse(review["can_merge"])
        self.assertIsNone(review["merged_sha256"])
        self.assertIsNone(review["merged"])
        self.assertEqual(len(review["conflicts"]), 1)
        problem = review["conflicts"][0]
        self.assertEqual(problem["path"], "/project/title")
        self.assertEqual(problem["reason"], "concurrent_edit")
        self.assertEqual(problem["ours_sha256"], sha256(
            json.dumps("Branche A", ensure_ascii=True,
                       separators=(",", ":")).encode("utf-8")).hexdigest())

    def test_delete_vs_edit_terrain_tile_is_conflict_not_resurrection(self):
        base = documents()
        ours = deepcopy(base)
        theirs = deepcopy(base)
        tiles = ours["content"]["missions"][0]["board"]["tiles"]
        self.assertGreaterEqual(len(tiles), 2)
        cell = list(tiles[-1]["pos"])
        tiles.pop()
        remote = theirs["content"]["missions"][0]["board"]["tiles"]
        remote[-1]["surface"] = "stone"
        if base["content"]["missions"][0]["board"]["tiles"][-1]["surface"] == "stone":
            remote[-1]["surface"] = "cobble"
        conflict = preview_three_way(base, ours, theirs)
        self.assertFalse(conflict["can_merge"])
        self.assertTrue(any(row["reason"] == "delete_vs_edit" and
                            row["path"].endswith(f"tiles[pos={cell[0]},{cell[1]}]")
                            for row in conflict["conflicts"]))

    def test_concurrent_reordering_requires_manual_review(self):
        base = documents()
        self.assertGreaterEqual(len(base["content"]["skills"]), 2)
        ours, theirs = deepcopy(base), deepcopy(base)
        ours["content"]["skills"][:2] = list(reversed(ours["content"]["skills"][:2]))
        theirs["content"]["skills"][0]["name"] = "Compétence modifiée"
        review = preview_three_way(base, ours, theirs)
        self.assertFalse(review["can_merge"])
        self.assertTrue(any(x["reason"] == "reorder_unsupported"
                            for x in review["conflicts"]))

    def test_bad_or_incompatible_documents_refused(self):
        base = documents()
        with self.assertRaises(SemanticMergeError) as error:
            preview_three_way(base, {"project": {}}, base)
        self.assertEqual(error.exception.code, "invalid_pair")
        bad = deepcopy(base)
        bad["project"]["campaigns"][0]["start_mission"] = "deleted"
        with self.assertRaises(SemanticMergeError):
            semantic_diff(base, bad)
        self.assertEqual(documents(), base)


class StudioMergeTests(unittest.TestCase):
    def setUp(self):
        self.base = documents()
        self.session = AuthoringSession.new(
            self.base["content"], self.base["project"])

    def test_preview_no_mutation_atomic_merge_undo_redo_save_and_open(self):
        before = self.session.snapshot().to_dict()
        local = self.session.preview_project(
            lambda project: {**project, "title": "Local"},
            kind="r24g-test")
        self.session.apply(local)
        theirs = deepcopy(self.base)
        theirs["project"]["subtitle"] = "Distante"
        review = preview_merge(self.session, self.base, theirs)
        self.assertTrue(review.can_apply)
        self.assertEqual(len(review.report["conflicts"]), 0)
        self.assertEqual(self.session.snapshot().to_dict()["project"]["subtitle"],
                         self.base["project"]["subtitle"])
        report_copy = deepcopy(review.report)
        report_copy["local_diff"].clear()
        self.assertTrue(review.report["local_diff"])
        transition = apply_merge(self.session, review)
        self.assertEqual(transition.kind, "r24g-semantic-merge")
        current = self.session.snapshot().to_dict()
        self.assertEqual(current["project"]["title"], "Local")
        self.assertEqual(current["project"]["subtitle"], "Distante")
        self.assertEqual(self.session.revision, 2)
        self.session.undo()
        self.assertEqual(self.session.snapshot().to_dict()["project"]["subtitle"],
                         self.base["project"]["subtitle"])
        self.session.redo()
        self.assertEqual(self.session.snapshot().to_dict()["project"], current["project"])
        with TemporaryDirectory() as folder:
            path = Path(folder) / "game.json"
            self.session.save_as(path)
            reopened = AuthoringSession.open(path)
            self.assertEqual(reopened.snapshot().to_dict()["project"], current["project"])
        self.assertEqual(before["project"]["title"], self.base["project"]["title"])

    def test_conflicts_and_no_change_cannot_be_forced(self):
        theirs = edit_title(self.base, "Other title")
        self.session.apply(self.session.preview_project(
            lambda project: {**project, "title": "Local title"}))
        review = preview_merge(self.session, self.base, theirs)
        self.assertFalse(review.can_apply)
        prior = self.session.snapshot().to_dict()
        with self.assertRaises(SemanticMergeError):
            apply_merge(self.session, review)
        self.assertEqual(self.session.snapshot().to_dict(), prior)
        nop = preview_merge(self.session, self.base, self.base)
        self.assertTrue(nop.report["can_merge"])
        self.assertTrue(nop.report["already_current"])
        with self.assertRaises(SemanticMergeError):
            apply_merge(self.session, nop)

    def test_stale_and_foreign_editor_preview_are_rejected(self):
        theirs = edit_title(self.base, "Theirs")
        review = preview_merge(self.session, self.base, theirs)
        self.assertTrue(review.can_apply)
        self.session.apply(self.session.preview_project(
            lambda project: {**project, "subtitle": "Intervening edit"}))
        with self.assertRaises(AuthoringError) as err:
            apply_merge(self.session, review)
        self.assertEqual(err.exception.code, "stale_revision")
        foreign = AuthoringSession.new(self.base["content"], self.base["project"])
        with self.assertRaises(AuthoringError) as err:
            apply_merge(foreign, review)
        self.assertEqual(err.exception.code, "foreign_preview")

    def test_headless_sdk_is_independent_of_gui(self):
        code = """
import sys
class Block:
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] in ('PySide6', 'PyQt5', 'PyQt6', 'tkinter'):
            raise AssertionError(name)
sys.meta_path.insert(0, Block())
from drawtemp.sdk import semantic_diff, preview_three_way, read_pair
from drawtemp.sdk.reference import reference_project
content, project = reference_project()
pair = {'content': content.to_dict(), 'project': project.to_dict()}
assert semantic_diff(pair, pair)['count'] == 0
assert preview_three_way(pair, pair, pair)['can_merge']
"""
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)


class LocalFileMergeTests(unittest.TestCase):
    def test_read_only_safe_pairs_and_cli_preview(self):
        base = documents()
        ours = edit_title(base, "Local")
        theirs = deepcopy(base)
        theirs["project"]["subtitle"] = "Other"
        with TemporaryDirectory() as folder:
            root = Path(folder)
            bp = save_pair(base, root / "base.json")
            lp = save_pair(ours, root / "local.json")
            tp = save_pair(theirs, root / "remote.json")
            self.assertEqual(read_pair(bp), base)
            self.assertEqual(read_pair(lp), ours)
            output = root / "review.json"
            args = [sys.executable, "-m", "drawtemp.sdk.r24g_cli",
                    "--base", str(bp), "--ours", str(lp),
                    "--theirs", str(tp), "--report", str(output)]
            before = {p: p.read_bytes() for p in (
                bp, bp.with_suffix(".game.json"),
                lp, lp.with_suffix(".game.json"),
                tp, tp.with_suffix(".game.json"))}
            process = subprocess.run(args, cwd=ROOT, capture_output=True,
                                     text=True, timeout=60)
            self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(report["can_merge"])
            self.assertNotIn("merged", report)
            self.assertEqual(len(report["local_diff"]), 1)
            self.assertEqual(len(report["remote_diff"]), 1)
            self.assertEqual({p: p.read_bytes() for p in before}, before)
            again = subprocess.run(args, cwd=ROOT, capture_output=True,
                                   text=True, timeout=60)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual(json.loads(output.read_text()), report)
            diff = subprocess.run(
                [sys.executable, "-m", "drawtemp.sdk.r24g_cli",
                 "--mode", "diff", "--base", str(bp), "--ours", str(lp)],
                cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual(diff.returncode, 0, diff.stderr)
            self.assertEqual(json.loads(diff.stdout)["local_changes"], 1)
            conflicting = edit_title(base, "Other")
            save_pair(conflicting, root / "collision.json")
            conflict = subprocess.run(
                [sys.executable, "-m", "drawtemp.sdk.r24g_cli",
                 "--base", str(bp), "--ours", str(lp),
                 "--theirs", str(root / "collision.json")],
                cwd=ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual(conflict.returncode, 2, conflict.stderr)
            self.assertEqual(json.loads(conflict.stdout)["conflicts"], 1)

    def test_duplicate_json_keys_symlinks_and_large_files_rejected(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            content = root / "bad.json"
            project = root / "bad.game.json"
            content.write_text('{"version":1,"version":1}', encoding="utf-8")
            project.write_text("{}", encoding="utf-8")
            with self.assertRaises(SemanticMergeError) as err:
                read_pair(content)
            self.assertEqual(err.exception.code, "duplicate_json_key")
            content.write_bytes(b"x" * (16 * 1024 * 1024 + 1))
            with self.assertRaises(SemanticMergeError) as err:
                read_pair(content)
            self.assertEqual(err.exception.code, "size_limit")
            link = root / "link.json"
            try:
                link.symlink_to(content)
            except (OSError, NotImplementedError):
                pass
            else:
                with self.assertRaises(SemanticMergeError) as err:
                    read_pair(link)
                self.assertEqual(err.exception.code, "unsafe_path")


@unittest.skipUnless(importlib.util.find_spec("PySide6") is not None,
                     "Optional Qt 6 is not installed")
class QtSemanticMergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(["r24g-qt"])

    def test_studio_uses_exact_live_session_and_one_undo_step(self):
        from PySide6.QtCore import QSettings
        from drawtemp.studio.qt_shell import StudioWindow
        base = documents()
        remote = deepcopy(base)
        remote["project"]["subtitle"] = "Remote UI"
        with TemporaryDirectory() as folder:
            bp = save_pair(base, Path(folder) / "base.json")
            tp = save_pair(remote, Path(folder) / "theirs.json")
            win = StudioWindow(
                AuthoringSession.new(base["content"], base["project"]),
                settings=QSettings(str(Path(folder) / "settings.ini"), QSettings.IniFormat))
            try:
                review = win.preview_semantic_merge(bp, tp)
                self.assertTrue(review.can_apply)
                self.assertEqual(win.session.revision, 0)
                win.apply_semantic_merge(review)
                self.assertEqual(win.session.revision, 1)
                self.assertEqual(win.session.snapshot().to_dict()["project"]["subtitle"],
                                 "Remote UI")
                win.undo()
                self.assertEqual(win.session.snapshot().to_dict()["project"], base["project"])
            finally:
                win.hide()
                win.deleteLater()


if __name__ == "__main__":
    unittest.main()
