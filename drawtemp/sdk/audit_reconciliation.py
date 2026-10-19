"""R48.A3 forensic comparison of local audit events and canonical snapshots.

The append-only audit is supporting evidence, never a source of Content or
GameProject. A matching digest does not prove authorship/completeness and a
clean hash chain cannot detect wholesale truncation without an externally
pinned head. Nothing here applies patches or repairs an interrupted save.
"""
from __future__ import annotations

from dataclasses import dataclass

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.collaboration import ProjectRevision, _checked
from drawtemp.sdk.project_audit import AuditError, LocalAuditLog
from drawtemp.sdk.semantic_review import fingerprint_pair

_NOT_SUPPLIED = object()


@dataclass(frozen=True)
class AuditReconciliation:
    state: str
    current_digest: str
    audit_head: str | None
    audited_after: str | None
    count: int
    unknown_records: tuple[int, ...]
    discontinuities: tuple[int, ...]
    anchored: bool

    def to_dict(self):
        return {
            "state": self.state, "current_digest": self.current_digest,
            "audit_head": self.audit_head, "audited_after": self.audited_after,
            "count": self.count, "unknown_records": list(self.unknown_records),
            "discontinuities": list(self.discontinuities),
            "anchored": self.anchored,
        }


def reconcile_audit(log: LocalAuditLog, session: AuthoringSession, *,
                    known_revisions=(), expected_head=_NOT_SUPPLIED
                    ) -> AuditReconciliation:
    """Read-only verification; report gaps rather than authorizing a repair.

    Pin the previously observed audit head by passing expected_head. This
    detects a removed log, a shorter valid prefix or changes between reviews.
    The result is advisory even if state='aligned': no mandatory audit log or
    complete snapshot inventory exists.
    """
    if not isinstance(log, LocalAuditLog) or not isinstance(session, AuthoringSession):
        raise TypeError("An audit log and a canonical AuthoringSession are required")
    snapshot = session.snapshot().to_dict()
    current_digest = fingerprint_pair(snapshot["content"], snapshot["project"])
    known = {current_digest}
    for revision in known_revisions:
        if not isinstance(revision, ProjectRevision):
            raise AuditError("invalid_revision", "Expected ProjectRevision evidence")
        content, project = _checked(revision)
        known.add(fingerprint_pair(content, project))
    records = log.entries()  # Complete integrity check on one detached snapshot.
    audit_head = records[-1]["digest"] if records else None
    anchored = expected_head is not _NOT_SUPPLIED
    if anchored and expected_head != audit_head:
        raise AuditError("audit_head_changed", "Audit head differs from pinned evidence")
    unknown = []
    gaps = []
    for i, row in enumerate(records):
        if row["before"] not in known or row["after"] not in known:
            unknown.append(row["sequence"])
        if i and row["before"] != records[i - 1]["after"]:
            gaps.append(row["sequence"])
    audited_after = records[-1]["after"] if records else None
    if not records:
        state = "empty"
    elif audited_after != current_digest:
        state = "drift"
    elif unknown or gaps:
        state = "partial_evidence"
    else:
        state = "aligned"
    return AuditReconciliation(state, current_digest, audit_head,
                               audited_after, len(records),
                               tuple(unknown), tuple(gaps), anchored)
