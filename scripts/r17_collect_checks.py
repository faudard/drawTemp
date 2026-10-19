"""Fetch all GitHub check-runs for one exact SHA to build R17.13 evidence.

Only CI uses network access. The generated JSON is still an unauthenticated
local snapshot: never treat it as cryptographic release attestation.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
from urllib.request import Request, urlopen


def collect(repo, revision, token, *, api="https://api.github.com"):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid GitHub repository")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Exact 40-digit SHA required")
    if not isinstance(token, str) or not token:
        raise ValueError("GitHub token required")
    all_runs = []
    count = None
    for page in range(1, 21):
        url = (api.rstrip("/") + "/repos/" + repo + "/commits/" + revision
               + "/check-runs?per_page=100&page=" + str(page))
        request = Request(url, headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "DrawTemp-R17-Release-Evidence",
        })
        with urlopen(request, timeout=25) as response:
            data = json.load(response)
        if (not isinstance(data, dict) or
                type(data.get("total_count")) is not int or
                not isinstance(data.get("check_runs"), list)):
            raise ValueError("Unexpected GitHub check-runs response")
        if count is None:
            count = data["total_count"]
        elif count != data["total_count"]:
            raise ValueError("Check-run count changed during pagination; rerun")
        for run in data["check_runs"]:
            if not isinstance(run, dict) or run.get("head_sha") != revision:
                raise ValueError("Check-run snapshot belongs to another SHA")
        all_runs.extend(data["check_runs"])
        if len(all_runs) >= count:
            if len(all_runs) != count:
                raise ValueError("Check-run snapshot count mismatch")
            return {"total_count": count, "check_runs": all_runs}
    raise ValueError("Too many check-run pages; release evidence incomplete")


def main(argv=None):
    parser = argparse.ArgumentParser(description="GitHub check runs for R17.13")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    payload = collect(args.repo, args.revision, os.getenv("GITHUB_TOKEN", ""))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print("Recorded " + str(payload["total_count"]) +
          " CI check runs for " + args.revision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
