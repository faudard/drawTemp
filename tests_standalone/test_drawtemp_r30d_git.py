"""R30.D local Git semantic review using throwaway repositories and actual commits."""
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import reference_project
from drawtemp.studio.r30_git_review import (
    GitReviewController, GitReviewError, LocalGitProject,
)


@unittest.skipUnless(shutil.which("git"), "Local Git executable required")
class GitReviewTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name) / "repository"
        self.root.mkdir()
        self.source = self.root / "projects" / "game.json"
        self.source.parent.mkdir()
        self.content, self.project = reference_project()
        AuthoringSession.new(self.content, self.project).save_as(self.source)
        self.git("init", "-q")
        self.git("config", "user.name", "DrawTemp R30 Test")
        self.git("config", "user.email", "r30-test@example.invalid")
        self.git("add", "projects/game.json", "projects/game.game.json")
        self.git("commit", "-qm", "base")
        self.git("tag", "base")
        self.session = AuthoringSession.new(self.content, self.project)

    def git(self, *args):
        completed = subprocess.run(
            ["git", "--no-pager", *args], cwd=self.root,
            capture_output=True, text=True, timeout=12,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return completed.stdout.strip()

    def commit_incoming(self, *, title=None, subtitle=None):
        session = AuthoringSession.open(self.source)
        session.apply(session.preview_project(
            lambda project: {**project,
                             **({"title": title} if title is not None else {}),
                             **({"subtitle": subtitle} if subtitle is not None else {})}))
        session.save()
        self.git("add", "projects/game.json", "projects/game.game.json")
        self.git("commit", "-qm", "incoming")

    def set_local(self, *, title=None, subtitle=None):
        self.session.apply(self.session.preview_project(
            lambda project: {**project,
                             **({"title": title} if title is not None else {}),
                             **({"subtitle": subtitle} if subtitle is not None else {})}))

    def test_immutable_snapshot_is_validated_and_read_only(self):
        self.commit_incoming(subtitle="Remote subtitle")
        repo = LocalGitProject(self.source)
        before_head = self.git("rev-parse", "HEAD")
        before_status = self.git("status", "--porcelain")
        base = repo.snapshot("base")
        latest = repo.snapshot("HEAD")
        self.assertNotEqual(base.commit, latest.commit)
        self.assertEqual(base.project["subtitle"], self.project.subtitle)
        self.assertEqual(latest.project["subtitle"], "Remote subtitle")
        self.assertEqual(before_head, self.git("rev-parse", "HEAD"))
        self.assertEqual(before_status, self.git("status", "--porcelain"))

    def test_disjoint_git_merge_applies_only_to_session_and_supports_undo(self):
        self.commit_incoming(subtitle="Remote subtitle")
        self.set_local(title="Local title")
        controller = GitReviewController(self.session, self.source)
        file_bytes = self.source.read_bytes()
        project_bytes = self.source.with_name("game.game.json").read_bytes()
        before_head = self.git("rev-parse", "HEAD")
        preview = controller.compare_refs("base", "HEAD")
        self.assertEqual(len(preview.conflicts), 0)
        self.assertTrue(preview.can_apply)
        changed = controller.apply({})
        self.assertEqual(changed.snapshot.project["title"], "Local title")
        self.assertEqual(changed.snapshot.project["subtitle"], "Remote subtitle")
        self.assertTrue(changed.snapshot.can_undo)
        restored = self.session.undo().snapshot
        self.assertEqual(restored.project["subtitle"], self.project.subtitle)
        self.assertEqual(restored.project["title"], "Local title")
        self.assertEqual(self.source.read_bytes(), file_bytes)
        self.assertEqual(self.source.with_name("game.game.json").read_bytes(), project_bytes)
        self.assertEqual(self.git("rev-parse", "HEAD"), before_head)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_conflicting_branch_needs_explicit_choice(self):
        self.commit_incoming(title="Remote title")
        self.set_local(title="Local title")
        controller = GitReviewController(self.session, self.source)
        preview = controller.compare_refs("base", "HEAD")
        self.assertEqual([conflict.path for conflict in preview.conflicts],
                         ["/project/title"])
        before = self.session.snapshot().to_dict()
        with self.assertRaisesRegex(ValueError, "explicit decision"):
            controller.apply({})
        self.assertEqual(self.session.snapshot().to_dict(), before)
        merged = controller.apply({"/project/title": "incoming"})
        self.assertEqual(merged.snapshot.project["title"], "Remote title")
        self.assertEqual(self.session.undo().snapshot.project["title"],
                         "Local title")

    def test_moved_ref_rejected_without_touching_editor(self):
        self.commit_incoming(subtitle="Remote subtitle")
        controller = GitReviewController(self.session, self.source)
        controller.compare_refs("base", "HEAD")
        self.git("commit", "--allow-empty", "-qm", "branch advanced")
        before = self.session.snapshot().to_dict()
        with self.assertRaises(GitReviewError) as caught:
            controller.apply({})
        self.assertEqual(caught.exception.code, "ref_moved")
        self.assertEqual(self.session.snapshot().to_dict(), before)

    def test_worktree_mutation_rejected(self):
        self.commit_incoming(subtitle="Remote subtitle")
        controller = GitReviewController(self.session, self.source)
        controller.compare_refs("base", "HEAD")
        self.source.write_bytes(self.source.read_bytes() + b" ")
        before = self.session.snapshot().to_dict()
        with self.assertRaises(GitReviewError) as caught:
            controller.apply({})
        self.assertEqual(caught.exception.code, "worktree_changed")
        self.assertEqual(self.session.snapshot().to_dict(), before)

    def test_live_session_revision_is_pinned(self):
        self.commit_incoming(subtitle="Remote subtitle")
        controller = GitReviewController(self.session, self.source)
        controller.compare_refs("base", "HEAD")
        self.set_local(title="Concurrent local edit")
        before = self.session.snapshot().to_dict()
        with self.assertRaisesRegex(ValueError, "Stale"):
            controller.apply({})
        self.assertEqual(self.session.snapshot().to_dict(), before)

    def test_git_injection_and_unknown_refs_rejected(self):
        repo = LocalGitProject(self.source)
        for ref in ("-c", "--help", "HEAD~1", "HEAD:path", "../HEAD",
                    "branch..other", "refs/heads/../../bad", "HEAD^{tree}",
                    "foo bar", "", "branch//other", "foo.lock", "a\nb"):
            with self.subTest(ref=ref), self.assertRaises(GitReviewError) as caught:
                repo.resolve_ref(ref)
            self.assertEqual(caught.exception.code, "invalid_ref")
        with self.assertRaises(GitReviewError):
            repo.snapshot("unknownbranch")

    def test_git_revision_missing_project_is_rejected(self):
        self.git("rm", "projects/game.game.json")
        self.git("commit", "-qm", "removed game project")
        with self.assertRaises(GitReviewError) as caught:
            LocalGitProject(self.source).snapshot("HEAD")
        # Working pair was deleted by git rm; a controller itself refuses it.
        self.assertIn(caught.exception.code, ("unsafe_worktree", "untracked_document"))

    def test_preflight_invalid_git_json_is_rejected(self):
        self.source.write_text('{"version":1,"version":1}', encoding="utf-8")
        self.git("add", "projects/game.json")
        self.git("commit", "-qm", "malformed content")
        repo = LocalGitProject(self.source)
        with self.assertRaises(GitReviewError) as caught:
            repo.snapshot("HEAD")
        self.assertEqual(caught.exception.code, "invalid_snapshot")

    def test_not_a_repository_is_rejected_without_writes(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            file = root / "game.json"
            AuthoringSession.new(self.content, self.project).save_as(file)
            with self.assertRaises(GitReviewError):
                LocalGitProject(file)


if __name__ == "__main__":
    unittest.main()
