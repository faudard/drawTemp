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
    squads = {}
    for agent in spec["agents"]:
        require(type(agent) is dict
                and {"id", "mode"} <= set(agent)
                and {"policies", "tree"} & set(agent)
                and not {"policies", "tree"} <= set(agent)
                and set(agent) <= {"id", "mode", "policies", "tree", "sensor", "squad"}
                and agent["mode"] in ("ct", "realtime"),
                "Invalid R37 AI agent contract")
        # Delegate identity and policy grammar to one R37.A authority.
        try:
            new_blackboard(agent["id"])
            if "tree" in agent:
                from drawtemp.sdk.behavior_tree import validate_behavior_tree
                validate_behavior_tree(agent["tree"])
            else:
                validate_policies(agent["policies"])
        except AIDecisionError as exc:
            raise RuleError("Invalid R37 AI policy: " + str(exc)) from exc
        require(agent["id"] not in seen, "Duplicate R37 AI actor")
        seen.add(agent["id"])
        if "sensor" in agent:
            from .ai_perception import validate_sensor
            validate_sensor(agent["sensor"])
            require(agent["mode"] == "realtime",
                    "R37.D sensors currently require a realtime R35 NPC")
        if "squad" in agent:
            from .ai_squad import MAX_SQUAD_MEMBERS, validate_squad
            binding = validate_squad(agent["squad"])
            require(agent["mode"] == "realtime" and "sensor" in agent,
                    "R37 squad members must have an R35 realtime sensor")
            squad_id = binding["id"]
            squads[squad_id] = squads.get(squad_id, 0) + 1
            require(squads[squad_id] <= MAX_SQUAD_MEMBERS,
                    "R37 squad must contain 1..8 authored agents")
        if agent["mode"] == "realtime":
            require(type(living_world) is dict
                    and type(living_world.get("npcs")) is list
                    and agent["id"] in {n.get("id") for n in living_world["npcs"]
                                        if type(n) is dict},
                    "Realtime R37 AI requires an R35 authored NPC")
            if "sensor" in agent:
                npc = next(n for n in living_world["npcs"]
                           if n["id"] == agent["id"])
                require(all("pos" in stop for stop in npc["schedule"]),
                        "R37 sensor requires a positioned R35 NPC schedule")
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
        return deepcopy(self.agents[actor_id])

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
        if "tree" in agent:
            from drawtemp.sdk.behavior_tree import evaluate_behavior_tree
            return evaluate_behavior_tree(context, self.blackboards[agent["id"]],
                                          agent["tree"])
        return evaluate_decision(context, self.blackboards[agent["id"]],
                                 agent["policies"])

    def remember(self, actor_id, changes, *, tick):
        agent = self.agent(actor_id)
        if "sensor" in agent and type(changes) is dict:
            if "suspicion" in changes:
                require(type(changes["suspicion"]) is int
                        and 0 <= changes["suspicion"] <= 3,
                        "R37 sensor suspicion must be an integer in 0..3")
            for field in ("alert", "heard_noise"):
                if field in changes:
                    require(type(changes[field]) is bool,
                            "R37 sensor alert/sound state must be boolean")
            for field in ("last_known_x", "last_known_y"):
                if field in changes:
                    require(type(changes[field]) is int
                            and 0 <= changes[field] < 32,
                            "R37 remembered coordinates must be grid cells")
            if "observation_kind" in changes:
                require(changes["observation_kind"] in ("none", "seen", "heard"),
                        "Invalid R37 observation source")
            if "last_known_scene" in changes:
                require(type(changes["last_known_scene"]) is str
                        and 0 < len(changes["last_known_scene"]) <= 64,
                        "Invalid R37 last-known scene")
            if "squad_source" in changes or "squad_signal" in changes:
                require("squad" in agent
                        and {"squad_source", "squad_signal"} <= set(changes)
                        and type(changes["squad_source"]) is str
                        and changes["squad_source"] != actor_id
                        and changes["squad_source"] in self.agents
                        and self.agents[changes["squad_source"]].get(
                            "squad", {}).get("id") == agent["squad"]["id"]
                        and type(changes["squad_signal"]) is str
                        and changes["squad_signal"] in ("seen", "heard"),
                        "Invalid R37 radio provenance")
        require(len(self.history) < MAX_WRITES,
                "R37 AI blackboard write ledger is full")
        require(not self.history or type(tick) is int
                and tick >= self.history[-1]["tick"],
                "R37 AI write events cannot go backwards in world time")
        # Validate first: an invalid update is never appended.
        updated = update_blackboard(self.blackboards[actor_id], changes, tick=tick)
        event = {"actor_id": actor_id, "tick": tick,
                 "changes": deepcopy(changes)}
        self.blackboards[actor_id] = updated
        self.history.append(event)
        return deepcopy(updated)

    def remember_batch(self, writes, *, tick):
        """Atomic multi-actor write, staged through exactly the normal ledger.

        No recipient is changed if any update is invalid or exceeds a budget.
        The saved format remains R37.B v1: a sorted series of ordinary writes.
        """
        require(type(writes) is list and 1 <= len(writes) <= MAX_AGENTS,
                "Invalid R37 squad memory batch")
        require(all(type(row) is dict and set(row) ==
                    {"actor_id", "changes"} for row in writes),
                "Invalid R37 squad memory event")
        identifiers = [row["actor_id"] for row in writes]
        require(identifiers == sorted(set(identifiers)),
                "R37 memory batch must have distinct ascending actor IDs")
        trial = deepcopy(self)
        results = []
        for row in writes:
            results.append(trial.remember(row["actor_id"], row["changes"], tick=tick))
        self.blackboards = trial.blackboards
        self.history = trial.history
        return results

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
