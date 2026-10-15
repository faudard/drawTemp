"""R1.9: Qt-independent, revision-checked background work for the 5.0 SDK.

Workers operate on *detached* canonical state. They never commit edits, touch
widgets, publish Qt signals or change the live simulation. Only the thread that
created the queue may collect results; callers must explicitly apply a returned
AuthoringPlan on that same thread.
"""
from __future__ import annotations

from concurrent.futures import CancelledError, ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, field
from threading import Event, Lock, get_ident

from drawtemp.sdk.authoring import AuthoringPlan, AuthoringSession
from drawtemp.sdk.simulation import Simulation, SimulationError


class WorkQueueError(RuntimeError):
    """Invalid use of the worker boundary, not a gameplay rule failure."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class WorkTicket:
    id: int
    kind: str
    source_revision: int
    _owner: object = field(repr=False, compare=False)


@dataclass(frozen=True)
class WorkResult:
    ticket: WorkTicket
    status: str
    payload: object = None
    error_code: str | None = None
    message: str = ""

    @property
    def ready(self):
        return self.status == "ready"


class _Progress:
    def __init__(self):
        self._lock = Lock()
        self._completed = 0
        self._total = 0

    def report(self, completed, total):
        with self._lock:
            self._completed, self._total = completed, total

    def snapshot(self):
        with self._lock:
            return self._completed, self._total


@dataclass
class _Pending:
    ticket: WorkTicket
    source: object
    cancelled: Event
    progress: _Progress
    future: object


class SdkWorkQueue:
    """Background authoring validation and bounded battle simulation.

    `submit_*`, `poll`, `cancel` and `close` belong to the constructing
    thread (normally the Qt GUI thread). `poll` never blocks: None means the
    task is still running. Results are one-shot and are rejected if the live
    handle's revision changed, even after edit/undo ABA. `close` cancels
    pending jobs; already-running user transforms must cooperate to stop early.
    """

    def __init__(self, *, max_workers=2):
        if type(max_workers) is not int or not 1 <= max_workers <= 8:
            raise ValueError("max_workers must be between 1 and 8")
        self._thread = get_ident()
        self._identity = object()
        self._executor = ThreadPoolExecutor(max_workers=max_workers,
                                            thread_name_prefix="drawtemp-sdk")
        self._jobs = {}
        self._next_id = 0
        self._closed = False

    def _check_thread(self):
        if get_ident() != self._thread:
            raise WorkQueueError("wrong_thread", "SDK results must be handled on the owning thread")

    def _submit(self, kind, source, revision, operation):
        self._check_thread()
        if self._closed:
            raise WorkQueueError("closed", "The work queue is closed")
        cancelled, progress = Event(), _Progress()
        ticket = WorkTicket(self._next_id, kind, revision, self._identity)
        self._next_id += 1
        future = self._executor.submit(operation, cancelled, progress)
        self._jobs[ticket.id] = _Pending(ticket, source, cancelled, progress, future)
        return ticket

    def submit_authoring(self, session: AuthoringSession, transform, *,
                         kind="async-authoring", mission_id=None, views=None):
        """Run a pure `(content, project) -> (content, project)` edit off-thread.

        Content and GameProject are copied before dispatch. Validation uses
        AuthoringSession's canonical validator and existing document formats.
        The original session is not captured by the worker closure.
        """
        self._check_thread()
        if not isinstance(session, AuthoringSession):
            raise TypeError("session must be AuthoringSession")
        if not callable(transform):
            raise TypeError("transform must be callable")
        snapshot = session.snapshot()
        documents = snapshot.to_dict()
        selected_views = tuple(views) if views is not None else None

        def operation(cancelled, progress):
            if cancelled.is_set():
                return None
            sandbox = AuthoringSession.new(documents["content"], documents["project"])
            options = {"kind": kind, "mission_id": mission_id}
            if selected_views is not None:
                options["views"] = selected_views
            result = sandbox.preview_pair(transform, **options)
            progress.report(1, 1)
            return None if cancelled.is_set() else result

        return self._submit("authoring", session, snapshot.revision, operation)

    def submit_simulation(self, simulation: Simulation, *, max_steps=100):
        """Run canonical deterministic AI simulation in an isolated session."""
        self._check_thread()
        if not isinstance(simulation, Simulation):
            raise TypeError("simulation must be Simulation")
        # Capture exclusively on the owner thread; never read the live engine
        # from a worker while a GUI action could change it.
        revision = simulation.snapshot().revision
        detached = deepcopy(simulation._session)

        def operation(cancelled, progress):
            if cancelled.is_set():
                return None
            sandbox = Simulation(detached)
            sandbox._revision = revision
            return sandbox.simulate(max_steps=max_steps, cancelled=cancelled.is_set,
                                    on_progress=progress.report)

        return self._submit("simulation", simulation, revision, operation)

    def _pending(self, ticket):
        self._check_thread()
        if not isinstance(ticket, WorkTicket) or ticket._owner is not self._identity:
            raise WorkQueueError("foreign_ticket", "Task belongs to another queue")
        job = self._jobs.get(ticket.id)
        if job is None:
            raise WorkQueueError("unknown_ticket", "Task has already been collected")
        return job

    def progress(self, ticket):
        """Return (completed, budget) without blocking the GUI thread."""
        return self._pending(ticket).progress.snapshot()

    def cancel(self, ticket):
        """Request cancellation; a cancelled task can never be committed."""
        job = self._pending(ticket)
        job.cancelled.set()
        job.future.cancel()

    def poll(self, ticket):
        """Return one terminal outcome or None, consuming completed tickets.

        Do not call `Future.result()` directly from a widget: this method
        handles errors, cancellation and the revision lease on the owner thread.
        """
        job = self._pending(ticket)
        if job.cancelled.is_set():
            result = WorkResult(ticket, "cancelled", error_code="cancelled")
        elif not job.future.done():
            return None
        elif job.source.revision != ticket.source_revision:
            result = WorkResult(ticket, "stale", error_code="stale_revision")
        else:
            try:
                payload = job.future.result()
                if payload is None:
                    result = WorkResult(ticket, "cancelled", error_code="cancelled")
                elif ticket.kind == "authoring":
                    # The detached worker plan uses a sandbox ownership token.
                    # Rebind only after the live session revision was checked.
                    payload = AuthoringPlan(
                        ticket.source_revision, payload.kind, payload.mission_id,
                        payload.views, payload.content, payload.project,
                        job.source._identity,
                    )
                    result = WorkResult(ticket, "ready", payload)
                else:
                    result = WorkResult(ticket, "ready", payload)
            except CancelledError:
                result = WorkResult(ticket, "cancelled", error_code="cancelled")
            except (SimulationError, Exception) as exc:
                result = WorkResult(ticket, "failed",
                                    error_code=getattr(exc, "code", "worker_failed"),
                                    message=str(exc))
        del self._jobs[ticket.id]
        return result

    def close(self):
        """Prevent new work and invalidate all tickets without waiting on UI."""
        self._check_thread()
        if self._closed:
            return
        self._closed = True
        for job in self._jobs.values():
            job.cancelled.set()
            job.future.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def __enter__(self):
        self._check_thread()
        return self

    def __exit__(self, *_):
        self.close()
