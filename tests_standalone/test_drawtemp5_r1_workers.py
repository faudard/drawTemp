"""R1.E worker regression helper and owner-thread contracts."""
from __future__ import annotations

from time import monotonic, sleep
import threading
import unittest

from drawtemp.sdk import AuthoringSession, SdkWorkQueue, WorkQueueError
from drawtemp.sdk.reference import reference_project


def wait_for(queue, ticket, *, timeout=10):
    """Poll without ever calling an authoring callback from a worker thread."""
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        result = queue.poll(ticket)
        if result.ready or result.error is not None:
            return result
        sleep(0.01)
    raise TimeoutError("SDK authoring worker did not finish")


class SdkWorkerTests(unittest.TestCase):
    def test_detached_result_requires_explicit_owner_commit(self):
        editor = AuthoringSession.new(*reference_project())
        initial = editor.snapshot()
        owner = threading.get_ident()
        seen = []

        def change(content, project):
            seen.append(threading.get_ident())
            content["missions"][0]["name"] = "Worker edit"
            return content, project

        with SdkWorkQueue(max_workers=1) as queue:
            ticket = queue.submit_authoring(editor, change)
            result = wait_for(queue, ticket)
            self.assertTrue(result.ready, result.message)
            self.assertNotEqual(seen, [owner])
            self.assertEqual(editor.snapshot(), initial)
            editor.apply(result.payload)
            self.assertEqual(editor.revision, initial.revision + 1)

    def test_stale_worker_result_does_not_override_owner_edit(self):
        editor = AuthoringSession.new(*reference_project())
        with SdkWorkQueue() as queue:
            ticket = queue.submit_authoring(
                editor, lambda content, project: (content, project))
            editor.undo() if editor.snapshot().can_undo else editor.apply(
                editor.preview_project(
                    lambda project: {**project, "title": "Already edited"}))
            result = wait_for(queue, ticket)
            self.assertFalse(result.ready)
            self.assertEqual(result.error, "stale_revision")
            self.assertEqual(editor.snapshot().to_dict()["project"]["title"],
                             "Already edited")

    def test_owner_enforcement(self):
        with SdkWorkQueue() as queue:
            errors = []
            def other_thread():
                try:
                    queue.poll("not a ticket")
                except WorkQueueError as exc:
                    errors.append(exc.code)
            thread = threading.Thread(target=other_thread)
            thread.start()
            thread.join()
            self.assertEqual(errors, ["wrong_thread"])


if __name__ == "__main__":
    unittest.main()
