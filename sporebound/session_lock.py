"""Portable fail-closed single-writer lock for long-session mutations.

A lock is intentionally never stolen, even if its recorded process seems
dead. An interrupted process requires explicit inspection/removal of the
.lock file by the owner before writes resume.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import time

from .model import RuleError


@contextmanager
def session_writer_lock(path):
    """Guard a complete read/modify/publish transaction with O_EXCL.

    The same slot MUST not have two simultaneous writers, including threads
    in one Python process. A lock left by a crash is a deliberate stop sign:
    never auto-delete or infer staleness from a PID (PID reuse is possible).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        handle = os.open(lock, flags, 0o600)
    except FileExistsError as exc:
        raise RuleError(f"Concurrent/stale session writer lock: {lock}. "
                        "Inspect the original process and lock before manual recovery.") from exc
    ownership = os.fstat(handle)
    try:
        try:
            data = json.dumps({"pid": os.getpid(), "created_epoch": time.time()},
                              separators=(",", ":")).encode("ascii")
            os.write(handle, data)
            os.fsync(handle)
        finally:
            os.close(handle)
        yield
    finally:
        # Only the context that created the lock removes it. Do not clear a
        # replaced/missing file blindly (manual cleanup is required then).
        try:
            current = lock.stat()
        except FileNotFoundError:
            current = None
        if current is not None:
            if (current.st_dev, current.st_ino) != (ownership.st_dev, ownership.st_ino):
                raise RuleError("Writer lock identity changed; refusing to delete another owner's lock")
            lock.unlink()
