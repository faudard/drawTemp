"""R8.17: crash cut-point matrix for the real SessionStore/LongSessionStore.

Run: python -m examples.persistence_fault_lab --seeds 1 7 --output r817.json

Each fault is an abruptly exiting *child process*, not an exception caught by
the save API. The parent reopens the on-disk artifacts in a fresh process,
verifies the exact replay, checks lock handling, and retries the same request
ID. No Tk, artificial gameplay state, or alternate save format is involved.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
from tempfile import TemporaryDirectory

from examples.reliability_gate import fixture
from sporebound.game_session import GameSession
from sporebound.long_session import LongSessionStore
from sporebound.model import RuleError, require
from sporebound.session_lock import session_writer_lock
from sporebound.storage import write_json

EXIT_CRASH = 79
_REQUEST = "r8.17.story.assault"
# Publication is always atomic. Inject a true process death either side of
# os.replace on the first journal, backup, full checkpoint, or compact clear.
CUTS = (
    ("temp", 1, "partial"),
    ("journal", 1, "before"),
    ("journal", 1, "after"),
    ("backup", 1, "before"),
    ("backup", 1, "after"),
    ("checkpoint", 1, "before"),
    ("checkpoint", 1, "after"),
    ("journal", 2, "before"),
    ("journal", 2, "after"),
)
TARGETS = {"journal": ".journal", "backup": ".bak",
           "checkpoint": ""}


def worker(path, cut, *, operation="choose_story_option"):
    """Worker writes one real action and *dies* at the selected fs cut."""
    require(operation in {"choose_story_option", "switch_front"},
            "Unsupported fault-lab operation")
    argument = "assault" if operation == "choose_story_option" else "walls"
    from unittest.mock import patch
    content, project = fixture()
    store = LongSessionStore(path, checkpoint_every=1)
    snapshot = store.load(content, project)
    target, ordinal, moment = cut
    seen = [0]
    original = os.replace

    if target == "temp":
        # Kill the actual process halfway through the temporary file's
        # write, before flush/fsync/replace. The original JSON must remain.
        import tempfile
        named_temp = tempfile.NamedTemporaryFile

        class PartialFile:
            def __init__(self, file):
                self.file = file

            def __enter__(self):
                self.file.__enter__()
                return self

            def __exit__(self, *args):
                return self.file.__exit__(*args)

            def write(self, data):
                self.file.write(data[:max(1, len(data) // 2)])
                self.file.flush()
                os._exit(EXIT_CRASH)

        def partial_temp(*args, **kwargs):
            file = named_temp(*args, **kwargs)
            prefix = kwargs.get("prefix", "")
            if prefix == Path(str(path) + ".journal").name + ".":
                return PartialFile(file)
            return file

        with patch("sporebound.storage.tempfile.NamedTemporaryFile",
                   side_effect=partial_temp):
            store.perform(snapshot, _REQUEST, operation, argument)
        raise AssertionError("Partial-temp cut was never reached")

    def replace(source, destination):
        dest = Path(destination)
        if dest == (Path(str(path) + TARGETS[target])
                    if target != "checkpoint" else Path(path)):
            seen[0] += 1
            if seen[0] == ordinal:
                if moment == "after":
                    original(source, destination)
                os._exit(EXIT_CRASH)
        return original(source, destination)

    # This is process-local; monkeypatching os.replace in a child never
    # affects the parent or another game process.
    with patch("sporebound.storage.os.replace", side_effect=replace):
        store.perform(snapshot, _REQUEST, operation, argument)
    raise AssertionError("Requested filesystem cut was never reached")


def _invoke_worker(path, cut, *, operation="choose_story_option"):
    cmd = [sys.executable, "-m", "examples.persistence_fault_lab",
           "--worker", str(path), "--cut", ".".join(map(str, cut)),
           "--operation", operation]
    result = subprocess.run(cmd, cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=45)
    require(result.returncode == EXIT_CRASH,
            "Crash worker missed cut %s: rc=%s stdout=%s stderr=%s" %
            (cut, result.returncode, result.stdout[-1000:],
             result.stderr[-1000:]))


def run_matrix(*, seeds=(1, 7)):
    require(isinstance(seeds, (tuple, list)) and bool(seeds) and
            all(type(s) is int for s in seeds), "Invalid fault-lab seeds")
    content, project = fixture()
    cases = []
    for seed in seeds:
        expected = GameSession.new(content, project, "main", seed=seed)
        before = expected.recording()
        expected.choose_story_option("assault")
        after = expected.recording()
        for cut in CUTS:
            with TemporaryDirectory(prefix="r817-") as folder:
                path = Path(folder) / "session.json"
                store = LongSessionStore(path, checkpoint_every=1)
                store.initialize(GameSession.new(content, project, "main",
                                                 seed=seed))
                saved = path.read_bytes()
                _invoke_worker(path, cut)
                lock = path.with_name(path.name + ".lock")
                require(lock.is_file(),
                        "Aborted writer failed to leave crash evidence")
                status = store.load_with_status(content, project)
                # Only death *before the FIRST journal publish* can lose an
                # uncommitted action. Once journal replace returned, recovery
                # must replay the action, including during checkpoint writes.
                committed = cut not in (("temp", 1, "partial"),
                                        ("journal", 1, "before"))
                expected_digest = after["digest"] if committed else before["digest"]
                require(status.session.recording()["digest"] == expected_digest,
                        "Persistence divergence at %s seed=%s" % (cut, seed))
                require(status.session.recording() == (after if committed else before),
                        "Full game state mismatch after crash")
                if not committed:
                    require(path.read_bytes() == saved,
                            "Uncommitted action changed primary checkpoint")
                # No silent stale-lock takeover, even when checkpoint/journal
                # is readable. A human must verify the writer is gone first.
                try:
                    store.perform(status.session, _REQUEST,
                                  "choose_story_option", "assault")
                except RuleError as exc:
                    require("lock" in str(exc).lower(),
                            "Wrong concurrent-writer rejection")
                else:
                    raise AssertionError("Crashed writer lock was stolen")
                if cut == ("temp", 1, "partial"):
                    require(list(Path(folder).glob("*.tmp")),
                            "Partial temporary file was not retained as evidence")
                lock.unlink()  # parent has already reaped the crashed child
                retried = store.perform(status.session, _REQUEST,
                                        "choose_story_option", "assault")
                require(retried.applied == (not committed),
                        "Retry applied a committed event twice, or lost one")
                final = store.load(content, project)
                require(final.recording() == after,
                        "Retry did not converge on the exact original outcome")
                require(len(final.progress.story_history) == 1,
                        "Narrative event duplicated after recovery")
                cases.append({
                    "seed": seed, "cut": ".".join(map(str, cut)),
                    "committed_at_cut": committed,
                    "recovered_digest": expected_digest,
                    "final_digest": final.recording()["digest"],
                    "checkpoint_sequence": status.sequence,
                    "journal_entries_replayed": status.applied,
                    "retry_applied": retried.applied,
                    "orphan_tmp_count": len(list(Path(folder).glob("*.tmp"))),
                    "verified": True,
                })
    return {"version": 1, "gate": "R8.17", "verified": True,
            "matrix": {"publication": "os.replace", "crash_exit_code": EXIT_CRASH,
                       "cut_points": len(CUTS)},
            "cases": cases}


def run_multifront_crash_gate():
    """Interrupt a first-time tactical focus switch and verify all fronts."""
    content, project = fixture()
    with TemporaryDirectory(prefix="r817-fronts-") as folder:
        path = Path(folder) / "fronts.json"
        store = LongSessionStore(path, checkpoint_every=1)
        session = GameSession.new(content, project, "main", seed=17)
        session.choose_story_option("assault")
        session.start_fronts({"gate": "gate", "walls": "walls"}, "gate",
                             specs={"gate": {"strength": 50, "opposition": 50},
                                    "walls": {"strength": 50, "opposition": 50}})
        session.execute({"kind": "end"})
        session.set_doctrine("walls", "assault")
        session.advance_fronts()
        before = session.recording()
        expected = GameSession.from_recording(before, content, project)
        expected.switch_front("walls")
        expected_recording = expected.recording()
        store.initialize(session)
        _invoke_worker(path, ("checkpoint", 1, "before"),
                       operation="switch_front")
        lock = path.with_name(path.name + ".lock")
        require(lock.is_file(), "Multi-front crash left no writer evidence")
        loaded = store.load_with_status(content, project)
        require(loaded.session.recording() == expected_recording,
                "Focused and offscreen fronts diverged after crash")
        require(loaded.session.fronts.history == expected.fronts.history,
                "Strategic history diverged after crash")
        require(loaded.session.fronts.timeline.state() ==
                expected.fronts.timeline.state(),
                "Offscreen front state diverged after crash")
        lock.unlink()  # the child has terminated and was reaped
        retry = store.perform(loaded.session, _REQUEST, "switch_front", "walls")
        require(not retry.applied, "A committed multi-front switch replayed twice")
        require(store.load(content, project).recording() == expected_recording,
                "Retry changed verified multi-front state")
        return {"verified": True, "mode": "fronts", "cut": "checkpoint.1.before",
                "final_digest": expected_recording["digest"],
                "strategic_history_events": len(expected.fronts.history)}


def run_concurrent_lock_gate():
    """A different OS process holding a slot blocks all other writers."""
    content, project = fixture()
    with TemporaryDirectory(prefix="r817-lock-") as folder:
        path = Path(folder) / "session.json"
        store = LongSessionStore(path, checkpoint_every=2)
        store.initialize(GameSession.new(content, project, "main"))
        ready, release = Path(folder) / "ready", Path(folder) / "release"
        child = subprocess.Popen(
            [sys.executable, "-m", "examples.persistence_fault_lab",
             "--holder", str(path), "--ready", str(ready),
             "--release", str(release)],
            cwd=Path(__file__).resolve().parents[1],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 20
            while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
                time.sleep(0.03)
            require(ready.is_file(), "Other process failed to acquire writer lock")
            original = store.load(content, project).recording()
            try:
                store.perform(store.load(content, project), _REQUEST,
                              "choose_story_option", "assault")
            except RuleError as exc:
                require("lock" in str(exc).lower(),
                        "Wrong lock refusal for competing process")
            else:
                raise AssertionError("Overlapping writers were accepted")
            require(store.load(content, project).recording() == original,
                    "Contender mutated the locked session")
            release.touch()
            out, err = child.communicate(timeout=20)
            require(child.returncode == 0,
                    "Lock holder failed: %s %s" % (out, err))
            require(not path.with_name(path.name + ".lock").exists(),
                    "Normal lock release left a stale lock")
            restored = store.load(content, project)
            require(store.perform(restored, _REQUEST,
                                  "choose_story_option", "assault").applied,
                    "Write did not resume after holder exited")
            return {"verified": True, "concurrent_writer_rejected": True,
                    "after_release_digest": store.load(content, project)
                                                 .recording()["digest"]}
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate(timeout=20)


def holder(path, ready, release):
    with session_writer_lock(path):
        Path(ready).touch()
        deadline = time.monotonic() + 20
        while not Path(release).exists() and time.monotonic() < deadline:
            time.sleep(0.03)
        require(Path(release).exists(), "Lock-holder timed out")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", nargs="+", type=int, default=[1, 7])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--cut")
    parser.add_argument("--operation", default="choose_story_option")
    parser.add_argument("--holder", type=Path)
    parser.add_argument("--ready", type=Path)
    parser.add_argument("--release", type=Path)
    args = parser.parse_args(argv)
    if args.worker is not None:
        require(bool(args.cut), "--cut is required with --worker")
        name, number, moment = args.cut.split(".")
        cut = (name, int(number), moment)
        require(cut in CUTS, "Unsupported cut point")
        worker(args.worker, cut, operation=args.operation)
        return 0
    if args.holder is not None:
        require(args.ready is not None and args.release is not None,
                "Lock holder needs ready/release paths")
        return holder(args.holder, args.ready, args.release)
    require(args.output is not None, "JSON report --output is required")
    report = run_matrix(seeds=args.seeds)
    report["concurrent_writers"] = run_concurrent_lock_gate()
    report["multifront_crash"] = run_multifront_crash_gate()
    write_json(args.output, report)
    print("R8.17 verified %s crash cut points across %s seeds" %
          (len(CUTS), len(args.seeds)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
