"""Headless, owner-thread-controlled SDK authoring work queue (R1.E).

Workers receive *detached values* only. They must never receive mutable
AuthoringSession internals, Qt objects, or a live editable project. Results
are validated and wrapped as an owned AuthoringPlan on the submitting thread;
only the editor may later commit the plan using AuthoringSession.apply().
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
from threading import get_ident
from typing import Any


class WorkQueueError(RuntimeError):
    """Stable error code for queue lifecycle, ownership or stale results."""

    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class WorkTicket:
    id: int
    kind: str = "authoring"


@dataclass(frozen=True)
class WorkResult:
    ready: bool
    payload: Any = None
    message: str = ""
    error: str | None = None


def _run_transform(transform, content, project):
    # Transform is a trusted authoring callback, never given a live session.
    changed = transform(deepcopy(content), deepcopy(project))
    if (not isinstance(changed, (tuple, list)) or len(changed) != 2):
        raise WorkQueueError("invalid_result", "Transform must return Content and GameProject")
    return deepcopy(changed[0]), deepcopy(changed[1])


class SdkWorkQueue:
    """Bounded worker pool with explicit polling and main-thread acceptance."""

    def __init__(self, *, max_workers=1):
        if type(max_workers) is not int or not 1 <= max_workers <= 32:
            raise WorkQueueError("invalid_budget", "Expected 1..32 workers")
        self._owner = get_ident()
        self._pool = ThreadPoolExecutor(max_workers=max_workers,
                                         thread_name_prefix="drawtemp-sdk")
        self._pending = {}
        self._next = 0
        self._closed = False

    def _require_owner(self):
        if get_ident() != self._owner:
            raise WorkQueueError("wrong_thread", "Poll and commit from the owner thread")

    def _require_open(self):
        if self._closed:
            raise WorkQueueError("closed", "Work queue has been closed")

    def submit_authoring(self, editor, transform):
        """Schedule a pure detached (content, project) transformer.

        Capture a frozen revision at submission. Intervening edits, including
        undo/redo ABA, invalidate the eventual result.
        """
        self._require_owner()
        self._require_open()
        if not callable(transform):
            raise WorkQueueError("invalid_transform", "Expected callable transformer")
        from .authoring import AuthoringSession
        if not isinstance(editor, AuthoringSession):
            raise WorkQueueError("invalid_editor", "Expected AuthoringSession")
        state = editor.snapshot().to_dict()
        future = self._pool.submit(_run_transform, transform,
                                   state["content"], state["project"])
        self._next += 1
        ticket = WorkTicket(self._next)
        self._pending[ticket.id] = {
            "future": future, "editor": editor,
            "revision": state["revision"], "result": None,
        }
        return ticket

    def poll(self, ticket):
        """Non-blocking result; never commits or modifies the live editor."""
        self._require_owner()
        self._require_open()
        if not isinstance(ticket, WorkTicket) or ticket.id not in self._pending:
            raise WorkQueueError("unknown_ticket", "Unknown work ticket")
        job = self._pending[ticket.id]
        if job["result"] is not None:
            return job["result"]
        if not job["future"].done():
            return WorkResult(False, message="pending")
        editor = job["editor"]
        if editor.revision != job["revision"]:
            result = WorkResult(False, message="Editor changed while worker ran",
                                error="stale_revision")
        elif job["future"].cancelled():
            result = WorkResult(False, message="Worker cancelled", error="cancelled")
        else:
            try:
                changed_content, changed_project = job["future"].result()
                from .authoring import AuthoringError
                # Build and validate only on the owner thread. If an edit has
                # intervened, AuthoringSession.apply will also reject the plan.
                plan = editor.preview_pair(
                    lambda _content, _project:
                        (deepcopy(changed_content), deepcopy(changed_project)),
                    kind="worker:authoring")
                result = WorkResult(True, payload=plan, message="ready")
            except Exception as exc:
                result = WorkResult(False, message=str(exc),
                                    error=getattr(exc, "code", "worker_failed"))
        job["result"] = result
        return result

    def cancel(self, ticket):
        self._require_owner()
        self._require_open()
        if not isinstance(ticket, WorkTicket) or ticket.id not in self._pending:
            raise WorkQueueError("unknown_ticket", "Unknown work ticket")
        job = self._pending[ticket.id]
        stopped = job["future"].cancel()
        if stopped:
            job["result"] = WorkResult(False, message="Worker cancelled",
                                       error="cancelled")
        return stopped

    def close(self, *, wait=True):
        self._require_owner()
        if not self._closed:
            self._closed = True
            self._pool.shutdown(wait=wait, cancel_futures=True)
            self._pending.clear()

    def __enter__(self):
        self._require_owner()
        self._require_open()
        return self

    def __exit__(self, *_exc):
        self.close()
        return False
