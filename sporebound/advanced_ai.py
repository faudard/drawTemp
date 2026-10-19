"""R37.B: opt-in AI policy registry and replay-checked blackboard ledger.

Project data lives in GameProject.extensions (canonical authoring). Session data
lives in GameSession's existing checksum-protected checkpoint. This module never
executes AI actions or replaces CT/realtime game rules.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.ai_decision import (
    AIDecisionError, evaluate_decision, new_blackboard, update_blackboard,
    validate_blackboard, validate_policies,
)
from .model import RuleError, require

EXTENSION = "org.drawtemp.advancedai"
VERSION = 1
MAX_AGENTS = 32
MAX_WRITES = 2048


def validate_advanced_ai(spec, *, living_world=None):
    """Validate authored opt-in policies before a project or session is loaded."""
    require(type(spec) is dict and set(spec) == {"version", "agents"}
            and type(spec["version"]) is int and spec["version"] == VERSION
            and type(spec["agents"]) is list
            and 1 <= len(spec["agents"]) <= MAX_AGENTS,
            "Invalid R37 advanced AI project document")
    seen = set()
    for agent in spec["agents"]:
        require(type(agent) is dict and set(agent) == {"id", "mode", "policies"}
                and agent["mode"] in ("ct", "realtime"),
                "Invalid R37 AI agent contract")
        # Delegate identity and policy grammar to one R37.A authority.
        try:
            new_blackboard(agent["id"])
            validate_policies(agent["policies"])
        except AIDecisionError as exc:
            raise RuleError("Invalid R37 AI policy: " + str(exc)) from exc
        require(agent["id"] not in seen, "Duplicate R37 AI actor")
        seen.add(agent["id"])
        if agent["mode"] == "realtime":
            require(living_world is not None
                    and agent["id"] in {n["id"] for n in living_world["npcs"]},
                    "Realtime R37 AI requires an R35 authored NPC")
    return deepcopy(spec)


class AdvancedAI:
    """Deterministic memory and read-only decisions; no separate game clock."""

    def __init__(self, spec, *, living_world=None):
        self.spec = validate_advanced_ai(spec, living_world=living_world)
        self.agents = {row["id"]: row for row in self.spec["agents"]}
        self.blackboards = {ident: new_blackboard(ident) for ident in self.agents}
        self.history = []

    def agent(self, actor_id):
        require(type(actor_id) is str and actor_id in self.agents,
                "Unknown R37 AI actor")
        return self.agents[actor_id]

    def state(self, actor_id=None):
        """Return only detached JSON; preview clients cannot mutate memory."""
        if actor_id is not None:
            self.agent(actor_id)
            return deepcopy(self.blackboards[actor_id])
        return {name: deepcopy(self.blackboards[name])
                for name in sorted(self.blackboards)}

    def preview(self, context):
        agent = self.agent(context["actor_id"])
        require(agent["mode"] == context["mode"], "R37 AI scene mode mismatch")
        return evaluate_decision(context, self.blackboards[agent["id"]],
                                 agent["policies"])

    def remember(self, actor_id, changes, *, tick):
        self.agent(actor_id)
        require(len(self.history) < MAX_WRITES,
                "R37 AI blackboard write ledger is full")
        # Validate first: an invalid update is never appended.
        updated = update_blackboard(self.blackboards[actor_id], changes, tick=tick)
        event = {"actor_id": actor_id, "tick": tick,
                 "changes": deepcopy(changes)}
        self.blackboards[actor_id] = updated
        self.history.append(event)
        return deepcopy(updated)

    def recording(self):
        return {"version": VERSION, "blackboards": self.state(),
                "history": deepcopy(self.history)}

    def restore(self, data):
        """Recompute ALL blackboards from writes, rejecting forged snapshots.

        A rehashed outer GameSession cannot fabricate an unexplained memory
        snapshot. The runtime's verified clock checks follow in GameSession.
        """
        require(type(data) is dict and set(data) ==
                {"version", "blackboards", "history"}
                and type(data["version"]) is int and data["version"] == VERSION
                and type(data["history"]) is list
                and len(data["history"]) <= MAX_WRITES
                and type(data["blackboards"]) is dict
                and set(data["blackboards"]) == set(self.agents),
                "Invalid R37 AI checkpoint shape")
        candidate = object.__new__(AdvancedAI)
        candidate.spec = self.spec
        candidate.agents = self.agents
        candidate.blackboards = {ident: new_blackboard(ident) for ident in self.agents}
        candidate.history = []
        for event in data["history"]:
            require(type(event) is dict and set(event) ==
                    {"actor_id", "tick", "changes"},
                    "Invalid R37 AI memory event")
            try:
                candidate.remember(event["actor_id"], event["changes"],
                                   tick=event["tick"])
            except (AIDecisionError, RuleError) as exc:
                raise RuleError("Invalid R37 AI memory journal: " + str(exc)) from exc
        for actor_id, snapshot in data["blackboards"].items():
            try:
                normalized = validate_blackboard(snapshot)
            except AIDecisionError as exc:
                raise RuleError("Invalid R37 AI blackboard: " + str(exc)) from exc
            require(normalized == candidate.blackboards[actor_id],
                    "R37 AI memory differs from replayed write journal")
        self.blackboards = candidate.blackboards
        self.history = candidate.history


__all__ = ["EXTENSION", "VERSION", "AdvancedAI", "validate_advanced_ai"]
