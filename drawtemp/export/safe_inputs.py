"""R80.A3: bounded regular-file snapshots for untrusted import inputs.

Reject observed symlinks, file replacement, truncated/oversized reads and
modifications during inspection. On systems supporting O_NOFOLLOW the last
component cannot switch to a symlink between lstat/open. This is not a
cross-process filesystem transaction or a Windows reparse-point guarantee.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat


class UnsafeSnapshotError(ValueError):
    """An import input cannot be safely snapshotted."""


def read_regular_snapshot(path, *, limit: int) -> bytes:
    """Read one bounded immutable byte snapshot, not a second path read.

    Source paths are supplied by a local operator; parent directory races
    still require OS-level sandboxing/ACLs. Callers must recheck hashes before
    commit and use exclusive publication of outputs.
    """
    if type(limit) is not int or limit < 1:
        raise UnsafeSnapshotError("Invalid read budget")
    source = Path(path)
    if source.is_symlink():
        raise UnsafeSnapshotError("Symlink input refused")
    try:
        before = source.stat(follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise UnsafeSnapshotError("Input is not a bounded regular file")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(source, flags)
        with os.fdopen(fd, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (not stat.S_ISREG(opened.st_mode) or opened.st_size > limit or
                    (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
                raise UnsafeSnapshotError("Input changed before read")
            result = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
        if len(result) > limit or len(result) != opened.st_size:
            raise UnsafeSnapshotError("Input exceeds budget or was truncated")
        if (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise UnsafeSnapshotError("Input modified during read")
        latest = source.stat(follow_symlinks=False)
        if (latest.st_dev, latest.st_ino, latest.st_size, latest.st_mtime_ns,
                latest.st_ctime_ns) != (
                opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns,
                opened.st_ctime_ns):
            raise UnsafeSnapshotError("Input changed after read")
        if source.is_symlink():
            raise UnsafeSnapshotError("Input became a symlink")
        return result
    except OSError as exc:
        raise UnsafeSnapshotError("Input cannot be read as a regular file") from exc
