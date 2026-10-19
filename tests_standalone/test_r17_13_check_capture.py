"""R17.13 GitHub check API pagination and commit-binding."""
from io import BytesIO
import json
import unittest
from unittest.mock import patch

from scripts.r17_collect_checks import collect

REV = "a" * 40


class _Response(BytesIO):
    def __init__(self, payload):
        super().__init__(json.dumps(payload).encode("utf-8"))


class GithubCheckCaptureTests(unittest.TestCase):
    def test_collect_all_pages_exact_revision(self):
        first = [{"id": n, "head_sha": REV} for n in range(100)]
        second = [{"id": 100, "head_sha": REV}]
        pages = [{"total_count": 101, "check_runs": first},
                 {"total_count": 101, "check_runs": second}]
        with patch("scripts.r17_collect_checks.urlopen",
                   side_effect=[_Response(p) for p in pages]) as fetch:
            found = collect("faudard/drawTemp", REV, "fake-local-test-token")
        self.assertEqual(found["total_count"], 101)
        self.assertEqual(len(found["check_runs"]), 101)
        self.assertEqual(fetch.call_count, 2)

    def test_rejects_foreign_sha(self):
        with patch("scripts.r17_collect_checks.urlopen",
                   return_value=_Response({"total_count": 1, "check_runs": [
                       {"head_sha": "b" * 40}]})):
            with self.assertRaisesRegex(ValueError, "another SHA"):
                collect("faudard/drawTemp", REV, "token")

    def test_rejects_incomplete_mutable_pagination(self):
        first = {"total_count": 101, "check_runs": [
            {"head_sha": REV} for _ in range(100)]}
        second = {"total_count": 102, "check_runs": [
            {"head_sha": REV} for _ in range(2)]}
        with patch("scripts.r17_collect_checks.urlopen",
                   side_effect=[_Response(first), _Response(second)]):
            with self.assertRaisesRegex(ValueError, "changed"):
                collect("faudard/drawTemp", REV, "token")

    def test_requires_valid_token_repo_and_sha_before_requests(self):
        for repo, sha, token in [
            ("user/../repo", REV, "token"),
            ("faudard/drawTemp", "not-a-sha", "token"),
            ("faudard/drawTemp", REV, ""),
        ]:
            with self.subTest(repo=repo, sha=sha, token=token):
                with self.assertRaises(ValueError):
                    collect(repo, sha, token)


if __name__ == "__main__":
    unittest.main()
