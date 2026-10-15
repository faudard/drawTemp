"""R1.9: no-GUI worker boundary, cancellation, revision leases and parity."""
import threading
import time
import unittest

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.sdk.simulation import Simulation, SimulationError
from drawtemp.sdk.workers import SdkWorkQueue, WorkQueueError


def wait_for(queue, ticket, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = queue.poll(ticket)
        if result is not None:
            return result
        time.sleep(0.005)
    raise AssertionError("Background job did not complete")


def rename(content, project):
    content["missions"][0]["name"] = "Village — async"
    return content, project


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()

    def test_authoring_plan_is_detached_validated_and_undoable(self):
        session = AuthoringSession.new(self.content, self.project)
        initial = session.snapshot()
        with SdkWorkQueue() as queue:
            ticket = queue.submit_authoring(session, rename, kind="map-edit", mission_id=MISSION)
            result = wait_for(queue, ticket)
            self.assertTrue(result.ready, (result.status, result.message))
            self.assertEqual(result.ticket.source_revision, initial.revision)
            self.assertEqual(queue._jobs, {})
            self.assertEqual(session.snapshot(), initial)  # no background mutation
            self.assertEqual(result.payload.kind, "map-edit")
            updated = session.apply(result.payload).snapshot
            self.assertEqual(updated.content["missions"][0]["name"], "Village — async")
            self.assertEqual(session.undo().snapshot.content, initial.content)
            self.assertEqual(session.redo().snapshot.content, updated.content)
            with self.assertRaises(WorkQueueError):
                queue.poll(ticket)

    def test_stale_after_edit_and_undo_aba(self):
        session = AuthoringSession.new(self.content, self.project)
        started, release = threading.Event(), threading.Event()

        def held(content, project):
            started.set()
            if not release.wait(10):
                raise RuntimeError("test gate timed out")
            return rename(content, project)

        with SdkWorkQueue(max_workers=1) as queue:
            ticket = queue.submit_authoring(session, held)
            self.assertTrue(started.wait(5))
            session.apply(session.preview_project(
                lambda project: {**project, "title": "Transient title"}))
            session.undo()
            self.assertEqual(session.snapshot().project["title"], self.project.title)
            release.set()
            result = wait_for(queue, ticket)
            self.assertEqual(result.status, "stale")
            self.assertEqual(result.error_code, "stale_revision")

    def test_cancelled_pending_work_does_not_publish(self):
        session = AuthoringSession.new(self.content, self.project)
        started, release = threading.Event(), threading.Event()

        def held(content, project):
            started.set()
            if not release.wait(10):
                raise RuntimeError("test gate timed out")
            return rename(content, project)

        with SdkWorkQueue(max_workers=1) as queue:
            original = session.snapshot()
            ticket = queue.submit_authoring(session, held)
            self.assertTrue(started.wait(5))
            queue.cancel(ticket)
            result = queue.poll(ticket)
            self.assertIsNotNone(result)
            self.assertEqual(result.status, "cancelled")
            self.assertEqual(session.snapshot(), original)
            release.set()  # the worker receives no reference to the live editor
            with self.assertRaises(WorkQueueError):
                queue.poll(ticket)

    def test_reject_validation_error_without_mutating_authoring(self):
        session = AuthoringSession.new(self.content, self.project)
        before = session.snapshot()
        with SdkWorkQueue() as queue:
            ticket = queue.submit_authoring(
                session, lambda content, project:
                ({**content, "missions": []}, project))
            outcome = wait_for(queue, ticket)
            self.assertEqual(outcome.status, "failed")
            self.assertEqual(outcome.error_code, "invalid_edit")
        self.assertEqual(session.snapshot(), before)

    def test_simulation_parity_progress_revision_and_purity(self):
        simulation = Simulation.new(self.content, self.project, "main", seed=17)
        simulation.choose_story_option("enter")
        simulation.start_mission(MISSION)
        simulation.execute({"kind": "interact", "unit": "jeanne", "object": "lever"})
        before = simulation.recording()
        progress = []
        expected = simulation.simulate(
            max_steps=700, on_progress=lambda done, total: progress.append((done, total)))
        self.assertEqual(progress[0], (0, 700))
        self.assertGreater(progress[-1][0], 0)
        self.assertLessEqual(progress[-1][0], 700)
        with SdkWorkQueue() as queue:
            ticket = queue.submit_simulation(simulation, max_steps=700)
            outcome = wait_for(queue, ticket)
            self.assertTrue(outcome.ready, (outcome.status, outcome.message))
            self.assertEqual(outcome.payload, expected)
        self.assertEqual(simulation.recording(), before)
        self.assertEqual(expected.battle["result"], "victory")

    def test_simulation_result_stale_after_live_command(self):
        simulation = Simulation.new(self.content, self.project, "main", seed=17)
        simulation.choose_story_option("enter")
        simulation.start_mission(MISSION)
        with SdkWorkQueue() as queue:
            ticket = queue.submit_simulation(simulation, max_steps=700)
            simulation.execute({"kind": "interact", "unit": "jeanne", "object": "lever"})
            outcome = wait_for(queue, ticket)
            self.assertEqual(outcome.status, "stale")
            self.assertEqual(outcome.error_code, "stale_revision")
        self.assertEqual(simulation.snapshot().battle["result"], None)

    def test_simulation_error_and_direct_cooperative_cancellation(self):
        simulation = Simulation.new(self.content, self.project, "main")
        with SdkWorkQueue() as queue:
            ticket = queue.submit_simulation(simulation, max_steps=1001)
            outcome = wait_for(queue, ticket)
            self.assertEqual(outcome.status, "failed")
            self.assertEqual(outcome.error_code, "invalid_budget")
        with self.assertRaises(SimulationError) as raised:
            simulation.simulate(cancelled=lambda: True)
        self.assertEqual(raised.exception.code, "cancelled")
        with self.assertRaises(SimulationError) as raised:
            simulation.simulate(cancelled=True)
        self.assertEqual(raised.exception.code, "invalid_callback")

    def test_wrong_thread_foreign_ticket_and_closed_queue(self):
        session = AuthoringSession.new(self.content, self.project)
        queue = SdkWorkQueue(max_workers=1)
        try:
            ticket = queue.submit_authoring(session, rename)
            errors = []

            def cross_thread():
                try:
                    queue.poll(ticket)
                except WorkQueueError as exc:
                    errors.append(exc.code)

            thread = threading.Thread(target=cross_thread)
            thread.start()
            thread.join(timeout=5)
            self.assertEqual(errors, ["wrong_thread"])
            with SdkWorkQueue() as other:
                with self.assertRaises(WorkQueueError) as error:
                    other.poll(ticket)
                self.assertEqual(error.exception.code, "foreign_ticket")
            self.assertTrue(wait_for(queue, ticket).ready)
            queue.close()
            queue.close()
            with self.assertRaises(WorkQueueError) as error:
                queue.submit_authoring(session, rename)
            self.assertEqual(error.exception.code, "closed")
        finally:
            queue.close()


if __name__ == "__main__":
    unittest.main()
