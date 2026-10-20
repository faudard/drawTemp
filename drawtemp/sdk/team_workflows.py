"""R78.A — opt-in, offline-first team review authority for canonical documents.

The host must authenticate stable actor IDs. Roles are not authentication.
ACLs and leases are process-local, not a distributed/cloud locking protocol.
No implicit save, network, Git mutation, or audit write occurs. The existing
R48/R30 history and semantic merge remain authoritative.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from secrets import token_hex
from threading import RLock
from time import monotonic

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.collaboration import make_revision
from drawtemp.sdk.project_history import HistoryReviewController, RevisionGraph
from drawtemp.sdk.project_audit import LocalAuditLog
from drawtemp.sdk.semantic_review import fingerprint_pair


class TeamWorkflowError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


_ROLES = frozenset(("owner", "editor", "reviewer", "viewer"))
_WRITERS = frozenset(("owner", "editor"))


def _identity(actor: str) -> str:
    if (not isinstance(actor, str) or not 1 <= len(actor) <= 80 or
            actor != actor.strip() or any(ord(ch) < 32 for ch in actor)):
        raise TeamWorkflowError("invalid_actor", "Use a nonempty stable actor ID (max 80 chars)")
    return actor


class TeamAccessPolicy:
    """Explicit local workspace membership. Never accepts self-asserted roles."""

    def __init__(self, members: dict[str, str]):
        if not isinstance(members, dict) or not members:
            raise TeamWorkflowError("invalid_policy", "Explicit workspace members required")
        self._lock = RLock()
        self._members = {}
        for actor, role in members.items():
            _identity(actor)
            if role not in _ROLES:
                raise TeamWorkflowError("invalid_role", "Unknown workspace role")
            self._members[actor] = role
        if "owner" not in self._members.values():
            raise TeamWorkflowError("invalid_policy", "At least one owner is required")

    def members(self) -> dict[str, str]:
        with self._lock:
            return dict(self._members)

    def require(self, actor: str, *, write: bool = False) -> str:
        _identity(actor)
        with self._lock:
            role = self._members.get(actor)
        if role is None or (write and role not in _WRITERS):
            raise TeamWorkflowError("access_denied", "Workspace permission denied")
        return role

    def assign(self, operator: str, actor: str, role: str | None):
        """Only an owner may change grants; the last owner cannot be removed."""
        _identity(actor)
        if role is not None and role not in _ROLES:
            raise TeamWorkflowError("invalid_role", "Unknown workspace role")
        with self._lock:
            if self._members.get(_identity(operator)) != "owner":
                raise TeamWorkflowError("access_denied", "Only owners can change roles")
            updated = dict(self._members)
            if role is None:
                updated.pop(actor, None)
            else:
                updated[actor] = role
            if "owner" not in updated.values():
                raise TeamWorkflowError("last_owner", "Cannot remove the last owner")
            self._members = updated


@dataclass(frozen=True)
class TeamLease:
    actor: str
    resource: str
    expires_at: float
    token: str = field(repr=False)


class TeamLeaseRegistry:
    """Exclusive in-process leases; token fencing prevents stale release/renew."""

    def __init__(self, policy: TeamAccessPolicy, *, clock=monotonic, limit=128):
        if not isinstance(policy, TeamAccessPolicy):
            raise TypeError("TeamAccessPolicy required")
        if type(limit) is not int or not 1 <= limit <= 1024:
            raise TeamWorkflowError("invalid_limit", "Lease capacity must be 1..1024")
        self.policy, self._clock, self._limit = policy, clock, limit
        self._lock = RLock()
        self._leases: dict[str, TeamLease] = {}

    @staticmethod
    def _validate(resource: str, ttl: float | None = None):
        # Content/GameProject merge is whole-document. Entity-level leases
        # must not be misrepresented as safe for this transaction.
        if resource != "project":
            raise TeamWorkflowError("invalid_resource", "R78.A requires a whole-project lease")
        if ttl is not None and (
                type(ttl) not in (float, int) or not isfinite(ttl) or
                not 0 < ttl <= 3600):
            raise TeamWorkflowError("invalid_ttl", "Lease TTL must be in (0, 3600] seconds")

    def _prune(self, now):
        for resource, lease in list(self._leases.items()):
            if lease.expires_at <= now:
                del self._leases[resource]

    def acquire(self, actor: str, *, resource="project", ttl=120) -> TeamLease:
        self._validate(resource, ttl)
        self.policy.require(actor, write=True)
        with self._lock:
            now = self._clock()
            self._prune(now)
            if resource in self._leases:
                raise TeamWorkflowError("lease_busy", "Resource already leased; release explicitly")
            if len(self._leases) >= self._limit:
                raise TeamWorkflowError("lease_limit", "Lease capacity exhausted")
            lease = TeamLease(actor, resource, now + ttl, token_hex(24))
            self._leases[resource] = lease
            return lease

    def require(self, actor: str, token: str, *, resource="project") -> TeamLease:
        self._validate(resource)
        with self._lock:
            self.policy.require(actor, write=True)
            now = self._clock()
            self._prune(now)
            lease = self._leases.get(resource)
            if (lease is None or lease.actor != actor or
                    not isinstance(token, str) or lease.token != token):
                raise TeamWorkflowError("invalid_lease", "No active lease for this actor/token")
            return lease

    def renew(self, actor: str, token: str, *, ttl=120) -> TeamLease:
        self._validate("project", ttl)
        with self._lock:
            self.require(actor, token)
            lease = TeamLease(actor, "project", self._clock() + ttl, token)
            self._leases["project"] = lease
            return lease

    def release(self, actor: str, token: str):
        with self._lock:
            self.require(actor, token)
            del self._leases["project"]


@dataclass(frozen=True)
class PendingTeamMerge:
    actor: str
    local_id: str
    incoming_id: str
    source_digest: str
    result_digest: str
    result_revision: int


class TeamMergeWorkspace:
    """Permissioned R48 review + explicit snapshot and audit checkpoints.

    Compare/apply uses one canonical AuthoringSession Undo transaction.
    DAG registration and durable audit are separate opt-in operations, never
    claimed to be one multi-resource atomic transaction.
    """

    def __init__(self, session: AuthoringSession, graph: RevisionGraph,
                 policy: TeamAccessPolicy, leases: TeamLeaseRegistry):
        if not isinstance(session, AuthoringSession) or not isinstance(graph, RevisionGraph):
            raise TypeError("AuthoringSession and RevisionGraph required")
        if leases.policy is not policy:
            raise TeamWorkflowError("policy_mismatch", "Leases must use this workspace's policy")
        self.session, self.graph, self.policy, self.leases = session, graph, policy, leases
        self.controller = HistoryReviewController(session, graph)
        self._preview = None
        self._pending: PendingTeamMerge | None = None
        self._registered_id: str | None = None

    def revisions(self, actor: str):
        """View verified revision metadata without raw file permissions."""
        self.policy.require(actor)
        return tuple(node.to_dict() for node in self.graph.nodes())

    def preview(self, actor: str, token: str, *, local_id: str,
                incoming_id: str, base_id: str | None = None):
        self.leases.require(actor, token)
        if self._pending is not None:
            raise TeamWorkflowError("pending_checkpoint", "Finish or acknowledge the previous merge")
        self._preview = None
        if local_id == incoming_id:
            raise TeamWorkflowError("same_revision", "Two distinct history nodes are required")
        review = self.controller.compare_history(local_id, incoming_id, base_id=base_id)
        self._preview = (actor, token, local_id, incoming_id, review)
        return review

    def apply(self, actor: str, token: str, review, decisions: dict[str, str]):
        self.leases.require(actor, token)
        pinned = self._preview
        if (pinned is None or pinned[:2] != (actor, token) or pinned[4] is not review):
            raise TeamWorkflowError("no_review", "Apply only your own pinned review")
        transition = self.controller.apply(review, decisions)
        result = transition.snapshot.to_dict()
        self._pending = PendingTeamMerge(
            actor, pinned[2], pinned[3], review.local_digest,
            fingerprint_pair(result["content"], result["project"]), result["revision"])
        self._registered_id = None
        self._preview = None
        return transition

    @property
    def pending(self):
        return self._pending

    def _check_pending(self, actor, token):
        self.leases.require(actor, token)
        pending = self._pending
        if pending is None or pending.actor != actor:
            raise TeamWorkflowError("no_merge", "No applied team merge by this actor")
        snapshot = self.session.snapshot().to_dict()
        if (snapshot["revision"] != pending.result_revision or
                fingerprint_pair(snapshot["content"], snapshot["project"]) != pending.result_digest):
            raise TeamWorkflowError("stale_merge", "Editor changed since team merge")
        return pending, snapshot

    def register(self, actor: str, token: str, *, label="Team merge"):
        """Explicit validated DAG checkpoint; never a file save or Git push."""
        pending, snap = self._check_pending(actor, token)
        if self._registered_id is not None:
            return self.graph.node(self._registered_id)
        parents = (pending.local_id, pending.incoming_id)
        digests = tuple(self.graph.node(parent).revision.digest for parent in parents)
        rev = make_revision(snap["content"], snap["project"],
                            author=actor, parents=digests)
        node = self.graph.add(rev, parents=parents, label=label)
        self._registered_id = node.node_id
        return node

    def append_audit(self, actor: str, token: str, log: LocalAuditLog, *, expected_head):
        """Explicit separate CAS append using the existing tamper-evident log."""
        pending, _snapshot = self._check_pending(actor, token)
        if self._registered_id is None:
            raise TeamWorkflowError("unregistered_merge", "Register the history checkpoint first")
        if not isinstance(log, LocalAuditLog):
            raise TypeError("LocalAuditLog required")
        event = log.append(expected_head=expected_head, actor=actor,
                           operation="r78_merge", resource="project",
                           before=pending.source_digest, after=pending.result_digest)
        self._pending = None
        self._registered_id = None
        return event

    def acknowledge_without_audit(self, actor: str, token: str):
        """Explicitly acknowledge missing audit evidence, not mark it logged."""
        self._check_pending(actor, token)
        if self._registered_id is None:
            raise TeamWorkflowError("unregistered_merge", "Register history before acknowledging missing audit")
        self._pending = None
        self._registered_id = None
