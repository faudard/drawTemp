"""R48.C2 — real process-level archive publish contention and orphan-lock gate.

Uses 'spawn' explicitly to test Windows, macOS and Linux with two independent
Python interpreters, not just threads/mock failures. Only a temporary folder
is affected; stale crash locks are inspected and removed by the TEST itself
after verifying fail-closed behavior. No automatic production lock stealing.
"""
from multiprocessing import get_context
from pathlib import Path
from queue import Empty
from tempfile import TemporaryDirectory
import os
import unittest

from drawtemp.sdk.collaboration import make_revision
from drawtemp.sdk.project_history import RevisionGraph
from drawtemp.sdk.project_history_store import LocalHistoryStore
from drawtemp.sdk.reference import reference_project
from sporebound.model import RuleError
from sporebound.session_lock import session_writer_lock


def _make_history(who):
    content, project = reference_project()
    graph = RevisionGraph()
    root_revision = make_revision(content, project, author="baseline")
    root = graph.add(root_revision, label="root")
    # Separate node identities ensure a successful process can be identified.
    next_revision = make_revision(
        content, project, author=who, parents=(root.revision.digest,))
    graph.add(next_revision, parents=(root.node_id,), label=who)
    return graph


def _independent_writer(path, who, start_signal, ready, results):
    try:
        graph = _make_history(who)
        ready.put(who)
        if not start_signal.wait(timeout=25):
            results.put((who, "timeout", "start event not received"))
            return
        published = LocalHistoryStore(path).save(graph, expected_digest=None)
        results.put((who, "published", published))
    except Exception as exc:
        results.put((who, "refused", type(exc).__name__ + ": " + str(exc)))


def _die_while_holding_lock(path):
    # Deliberate test process termination bypasses the context manager's
    # cleanup; production API must NOT quietly steal this abandoned lock.
    with session_writer_lock(path):
        os._exit(37)


class IndependentWriterTests(unittest.TestCase):
    def test_two_real_processes_cannot_both_publish_same_unseen_archive(self):
        with TemporaryDirectory(prefix="drawtemp-r48c-race-") as directory:
            path = Path(directory) / "versions.r48.json"
            ctx = get_context("spawn")
            start = ctx.Event()
            ready = ctx.Queue()
            results = ctx.Queue()
            children = [
                ctx.Process(target=_independent_writer,
                            args=(str(path), who, start, ready, results))
                for who in ("alice", "bob")
            ]
            for child in children:
                child.start()
            try:
                seen = {ready.get(timeout=35), ready.get(timeout=35)}
                self.assertEqual(seen, {"alice", "bob"})
                start.set()
                rows = [results.get(timeout=35), results.get(timeout=35)]
            finally:
                start.set()
                for child in children:
                    child.join(timeout=10)
                    if child.is_alive():
                        child.terminate()
                        child.join(timeout=10)
            self.assertTrue(all(child.exitcode == 0 for child in children))
            successful = [row for row in rows if row[1] == "published"]
            refused = [row for row in rows if row[1] == "refused"]
            self.assertEqual(len(successful), 1, rows)
            self.assertEqual(len(refused), 1, rows)
            self.assertIn(refused[0][0], ("alice", "bob"))
            self.assertNotEqual(successful[0][0], refused[0][0])
            graph, digest = LocalHistoryStore(path).load()
            self.assertEqual(digest, successful[0][2])
            self.assertEqual(len(graph), 2)
            self.assertEqual(graph.nodes()[1].revision.author, successful[0][0])
            self.assertFalse(path.with_name(path.name + ".lock").exists())

    def test_abrupt_process_exit_leaves_stale_lock_and_refuses_publish(self):
        with TemporaryDirectory(prefix="drawtemp-r48c-abrupt-") as directory:
            path = Path(directory) / "versions.r48.json"
            ctx = get_context("spawn")
            child = ctx.Process(target=_die_while_holding_lock,
                                args=(str(path),))
            child.start()
            child.join(timeout=35)
            if child.is_alive():
                child.terminate()
                child.join(timeout=10)
                self.fail("Lock-owner child did not terminate as expected")
            self.assertEqual(child.exitcode, 37)
            lock = path.with_name(path.name + ".lock")
            self.assertTrue(lock.is_file())
            store = LocalHistoryStore(path)
            graph = _make_history("alice")
            with self.assertRaises(RuleError):
                store.save(graph, expected_digest=None)
            self.assertFalse(path.exists())
            # Only the TEST OWNER performs explicit forensic/manual cleanup.
            self.assertIn('"pid"', lock.read_text(encoding="utf-8"))
            lock.unlink()
            digest = store.save(graph, expected_digest=None)
            self.assertEqual(LocalHistoryStore(path).inspect(), digest)


if __name__ == "__main__":
    unittest.main()
