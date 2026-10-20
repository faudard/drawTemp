"""R80.A2 optional two-runtime gate: generate real R16 saves, read with current Core.

Requires an independently checked out Git worktree at the exact R16 merge
commit. The historical source executes *only* in a separate Python process
and writes three saves into an isolated temporary directory. This is CI
compatibility evidence, not permission to run arbitrary untrusted projects.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

from .r80_historical import (
    HISTORICAL_COMMIT, HistoricalRegressionError, _assert, load_pinned_sources,
)

_GENERATE = """
import sys
from pathlib import Path
from drawtemp.core import GameSession
from drawtemp.sdk.reference import MISSION, reference_project
from sporebound.persistence import SessionStore

output = Path(sys.argv[1])
content, project = reference_project()
session = GameSession.new(content, project, "main", seed=17)
session.save(output / "r16-campaign-v1.json")
session.choose_story_option("enter")
session.start_mission(MISSION)
session.execute({"kind": "interact", "unit": "jeanne", "object": "lever"})
session.save(output / "r16-battle-v1.json")
SessionStore(output / "r16-battle-v2.json").save(session)
"""


def run_cross_revision(historical_checkout):
    from drawtemp.core import GameSession, RuleError
    from drawtemp.sdk.reference import reference_project
    from drawtemp.sdk.replay import verify_recording
    from sporebound.persistence import SessionStore

    path = Path(historical_checkout)
    if path.is_symlink() or not path.is_dir():
        raise HistoricalRegressionError("Historical checkout must be a real directory")
    path = path.resolve(strict=True)
    # Do not accidentally trust a random directory named after the R16 commit.
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=20)
    except (subprocess.SubprocessError, OSError) as exc:
        raise HistoricalRegressionError("Cannot authenticate historical Git checkout") from exc
    _assert(completed.stdout.strip() == HISTORICAL_COMMIT,
            "Historical checkout revision is not the pinned R16 commit")
    load_pinned_sources(path)  # Pin four actual source blobs, before execution.
    content, project = reference_project()  # Current checkout's canonical reader.
    hashes = {}
    with TemporaryDirectory(prefix="r80-a2-actual-r16-") as directory:
        output = Path(directory)
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(path)
        environment["PYTHONNOUSERSITE"] = "1"
        try:
            historic = subprocess.run(
                [sys.executable, "-c", _GENERATE, str(output)],
                cwd=path, env=environment, check=False,
                capture_output=True, text=True, timeout=120)
        except (subprocess.SubprocessError, OSError) as exc:
            raise HistoricalRegressionError("Historical R16 runtime launch failed") from exc
        if historic.returncode:
            raise HistoricalRegressionError(
                "Historical R16 runtime rejected the seed/test scenario: " +
                historic.stderr[-1000:])
        campaign_path = output / "r16-campaign-v1.json"
        battle_path = output / "r16-battle-v1.json"
        v2_path = output / "r16-battle-v2.json"
        for file in (campaign_path, battle_path, v2_path):
            _assert(file.is_file() and not file.is_symlink() and
                    file.stat().st_size <= 8 * 1024 * 1024,
                    "Historical save is missing, linked or oversized: " + file.name)
            hashes[file.name] = sha256(file.read_bytes()).hexdigest()
        # The *new* runtime must consume old bytes without rewriting them.
        for source, expected_mode in ((campaign_path, "campaign"),
                                      (battle_path, "battle")):
            try:
                old = json.loads(source.read_text(encoding="utf-8"))
                _assert(old.get("kind") == "game_session" and old.get("version") == 1,
                        "R16 v1 save envelope changed")
                restored = verify_recording(old, content, project)
                _assert(restored.mode == expected_mode,
                        "R16 session mode mismatch: " + source.name)
                _assert(restored.recording() == old,
                        "Current runtime normalized away historic session fields")
            except (RuleError, ValueError, TypeError, KeyError) as exc:
                raise HistoricalRegressionError(
                    "Current runtime cannot read R16 " + source.name) from exc
        try:
            result = SessionStore(v2_path).load_with_status(content, project)
            _assert(result.source == "primary" and result.sequence == 1,
                    "R16 v2 checkpoint sequence failed")
            _assert(result.session.recording() == json.loads(battle_path.read_text(
                encoding="utf-8")), "R16 v2 replay diverges from v1 battle save")
            _assert(SessionStore(v2_path).load(content, project).recording() ==
                    result.session.recording(), "Repeated historical checkpoint load changed state")
        except (RuleError, OSError, ValueError, KeyError) as exc:
            raise HistoricalRegressionError("Current runtime cannot read R16 v2") from exc
        # Unsupported checkpoint revisions are never silently upgraded.
        invalid = json.loads(v2_path.read_text(encoding="utf-8"))
        invalid["version"] = 99
        invalid_path = output / "unknown-v2.json"
        invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
        try:
            SessionStore(invalid_path).load(content, project)
        except RuleError:
            pass
        else:
            raise HistoricalRegressionError("Future checkpoint schema accepted")
        for source in (campaign_path, battle_path, v2_path):
            _assert(sha256(source.read_bytes()).hexdigest() == hashes[source.name],
                    "Inspecting R16 save overwrote original bytes")
    return {
        "kind": "drawtemp-r80a2-cross-revision",
        "schema": 1,
        "producer_commit": HISTORICAL_COMMIT,
        "producer": "historical-r16-python-runtime",
        "consumer": "current-branch-python-runtime",
        "checked_formats": ["game_session_v1_campaign",
                            "game_session_v1_battle",
                            "session_checkpoint_v2_battle"],
        "producer_save_sha256": hashes,
        "result": "passed",
        "release_certified": False,
        "tag_allowed": False,
        "limitations": [
            "Checks R16 -> current Core only; no other user-released versions",
            "No installer, GUI, GPU, external creator, or real-device approval",
            "No reward completion deduplication or long-session crash-recovery proof",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-checkout", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_cross_revision(args.historical_checkout)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False,
                                          indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
    except (HistoricalRegressionError, OSError, ValueError) as exc:
        print("R80.A2 cross-version gate blocked: " + str(exc), file=sys.stderr)
        return 2
    print("R80.A2 R16 -> current saves verified (12.0 release remains NO-GO)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
