"""R5.14: deterministic, in-memory campaign route sandbox (no tactical replay).

A simulation is a tree of immutable-in-practice Campaign snapshots. Every action
uses existing StoryBook choices, Campaign Flow gates/consequences and mission
next_missions. Hypothetical battle outcomes are NEVER declared verified battles.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from .campaign_flow import (available_missions, inspect_campaign, settle,
                            verify_save)
from .model import RuleError, require
from .narrative import StoryBook


@dataclass(frozen=True)
class SimulationNode:
    id: int
    parent: int | None
    depth: int
    action: str
    progress: object
    verified_battle: bool = False  # Deliberately never true in this sandbox.


def _differences(before, after):
    """Stable, JSON-compatible leaf-level changes; no edits to either side."""
    result = []

    def visit(left, right, path):
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right)):
                label = path + "." + str(key) if path else str(key)
                if key not in left:
                    result.append({"path": label, "before": None, "after": deepcopy(right[key])})
                elif key not in right:
                    result.append({"path": label, "before": deepcopy(left[key]), "after": None})
                else:
                    visit(left[key], right[key], label)
        elif left != right:
            result.append({"path": path, "before": deepcopy(left), "after": deepcopy(right)})

    visit(before, after, "")
    return result


class CampaignSimulation:
    """Explore branch alternatives without mutating user saves or authoring data.

    Nodes only exist in RAM; no slot, GameSession checkpoint or project save is
    created. Future paths fork from any selected prior node. Invalid operations
    leave both the selected cursor and the entire tree unchanged.
    """

    def __init__(self, content, project, campaign_id, *, progress=None,
                 max_nodes=512, max_depth=96):
        require(type(max_nodes) is int and 2 <= max_nodes <= 4096,
                "Invalid sandbox node budget")
        require(type(max_depth) is int and 1 <= max_depth <= 256,
                "Invalid sandbox depth budget")
        project.validate(content)
        require(project.campaign(campaign_id) is not None,
                "Unknown sandbox campaign")
        self.content = deepcopy(content)
        self.project = deepcopy(project)
        self.campaign_id = campaign_id
        # Paths from a loaded slot cannot be certified by replaying a new game.
        self._started_from_progress = progress is not None
        self.story = StoryBook(self.project.story, self.content,
                               self.project.campaigns)
        self.flow = self.project.campaign_flow
        self.max_nodes = max_nodes
        self.max_depth = max_depth
        root = (deepcopy(progress) if progress is not None
                else self.project.new_game(campaign_id, self.content))
        verify_save(root, self.flow)
        self.story.initialize(root, campaign_id)
        require(set(root.unlocked + root.completed) <= set(self.content.missions),
                "Sandbox contains unknown missions")
        self._nodes = {0: SimulationNode(0, None, 0, "Initial state", root)}
        self._current = 0
        self._next_id = 1

    @property
    def cursor(self):
        return self._current

    @property
    def size(self):
        return len(self._nodes)

    def _node_raw(self, node_id=None):
        node_id = self._current if node_id is None else node_id
        require(type(node_id) is int and node_id in self._nodes,
                "Unknown campaign simulation node")
        return self._nodes[node_id]

    def node(self, node_id=None):
        """Public node metadata is a copy, including its Campaign progress."""
        return deepcopy(self._node_raw(node_id))

    def snapshot(self, node_id=None):
        """Return a deep copy so external consumers cannot mutate branch state."""
        return deepcopy(self._node_raw(node_id).progress)

    def inspect(self, node_id=None):
        progress = self.snapshot(node_id)
        result = inspect_campaign(progress, self.flow)
        result["story_pending"] = progress.story_pending
        result["choices"] = [choice["id"] for choice in self.story.choices(progress)]
        result["node"] = self._node_raw(node_id).id
        result["symbolic_only"] = True
        return result

    def actions(self, node_id=None):
        """Every offered action is conditional on the exact node state."""
        progress = self._node_raw(node_id).progress
        if progress.story_pending:
            return [{"kind": "choice", "id": c["id"], "scene": progress.story_pending,
                     "label": c["label"]} for c in self.story.choices(progress)]
        actions = []
        for mission_id in available_missions(progress, self.flow):
            actions.append({"kind": "mission", "id": mission_id,
                            "outcome": "victory", "symbolic": True})
            actions.append({"kind": "mission", "id": mission_id,
                            "outcome": "defeat", "symbolic": True})
        return actions

    def tree(self):
        return [{"id": node.id, "parent": node.parent, "depth": node.depth,
                 "action": node.action, "current": node.id == self._current,
                 "verified_battle": False}
                for node in self._nodes.values()]

    def select(self, node_id):
        self._node_raw(node_id)  # validate before changing cursor
        self._current = node_id
        return self.inspect()

    def _publish(self, progress, action):
        parent = self._node_raw()
        require(len(self._nodes) < self.max_nodes, "Campaign simulation node budget reached")
        require(parent.depth < self.max_depth, "Campaign simulation depth reached")
        verify_save(progress, self.flow)
        require(set(progress.unlocked + progress.completed) <= set(self.content.missions),
                "Simulation created unknown mission reference")
        # Snapshot isolation: even a later caller modifying an inspect result
        # or the input progress cannot rewrite a historical branch.
        node = SimulationNode(self._next_id, parent.id, parent.depth + 1, action,
                              deepcopy(progress))
        self._nodes[node.id] = node
        self._next_id += 1
        self._current = node.id
        return self.inspect()

    def choose(self, choice_id):
        current = self._node_raw().progress
        require(bool(current.story_pending), "No pending scene to choose")
        require(any(c["id"] == choice_id for c in self.story.choices(current)),
                "Story choice is not currently available")
        updated = self.story.choose(current, choice_id)
        return self._publish(updated, "choice:" + current.story_pending + "/" + choice_id)

    def resolve(self, mission_id, outcome):
        """Hypothetical result: no Battle commands, XP, loot or replay evidence."""
        current = self.node().progress
        require(not current.story_pending, "Resolve the pending scene first")
        require(mission_id in available_missions(current, self.flow),
                "Mission is not currently available")
        require(outcome in ("victory", "defeat"), "Unknown symbolic mission outcome")
        updated = deepcopy(current)
        if outcome == "victory":
            updated.completed.append(mission_id)
            # Authored fixed reward is knowable, tactical loot and per-unit XP
            # are not. Keep explicit note in the UI/report about this boundary.
            updated.gold += self.content.missions[mission_id].reward
            require(0 <= updated.gold <= 1000000, "Symbolic reward exceeds gold cap")
            if mission_id in self.story.after:
                self.story.after_victory(updated, mission_id)
            else:
                for successor in self.content.missions[mission_id].next_missions:
                    if successor not in updated.unlocked:
                        updated.unlocked.append(successor)
        updated = settle(updated, self.flow, mission_id, outcome,
                         content=self.content)
        return self._publish(updated, f"mission:{mission_id}:{outcome} (symbolic)")

    def fork(self, label="Alternative"):
        """Named branch checkpoint, even before taking another choice."""
        require(isinstance(label, str) and 0 < len(label.strip()) <= 80,
                "Invalid simulation branch name")
        return self._publish(self.snapshot(), "fork:" + label.strip())

    def path(self, node_id=None):
        node = self._node_raw(node_id)
        result = []
        while node is not None:
            result.append(node.id)
            node = self._nodes[node.parent] if node.parent is not None else None
        return list(reversed(result))

    def compare(self, a, b):
        left, right = self._node_raw(a), self._node_raw(b)
        lhs, rhs = self.path(a), self.path(b)
        common = 0
        for i, j in zip(lhs, rhs):
            if i != j:
                break
            common = i
        before = inspect_campaign(left.progress, self.flow)
        after = inspect_campaign(right.progress, self.flow)
        return {"left": a, "right": b, "common_ancestor": common,
                "left_path": [self._nodes[i].action for i in lhs if i != 0],
                "right_path": [self._nodes[i].action for i in rhs if i != 0],
                "changed": _differences(before, after),
                "left_endings": before["endings"],
                "right_endings": after["endings"],
                "symbolic_only": True,
                "scope": "No Battle replay, tactical XP, loot or world travel certification"}

    def certification_plan(self, node_id=None, *, seed=7):
        """Convert a *candidate* route to replay instructions, not evidence.

        The R5.15 runner must still execute all Battle commands, match expected
        outcomes and independently verify checkpoints before certifying.
        """
        require(not self._started_from_progress,
                "Cannot certify a partial loaded save from a fresh-game root")
        require(type(seed) is int and 0 <= seed <= 2147483647,
                "Invalid certification seed")
        destination = self._node_raw(node_id)
        steps = []
        for nid in self.path(destination.id)[1:]:
            action = self._nodes[nid].action
            if action.startswith("fork:"):
                continue
            if action.startswith("choice:"):
                require("/" in action, "Malformed branch choice identity")
                steps.append({"kind": "choice", "id": action.rsplit("/", 1)[1]})
            elif action.startswith("mission:") and action.endswith(" (symbolic)"):
                mid, outcome = action[len("mission:"):-len(" (symbolic)")].rsplit(":", 1)
                steps.append({"kind": "mission", "id": mid, "outcome": outcome})
            else:
                raise RuleError("Unrecognized branch action in certification plan")
        require(any(step["kind"] == "mission" for step in steps),
                "Certification requires an actual tactical battle")
        preview = inspect_campaign(destination.progress, self.flow)
        return {"id": "route_" + str(destination.id),
                "campaign": self.campaign_id, "seed": seed,
                "steps": steps,
                "expect": {"completed": list(preview["missions"]["completed"]),
                           "endings": list(preview["endings"])}}

    def coverage(self):
        """Observed paths in THIS interactive sandbox only, never exhaustive QA."""
        witnessed = set()
        missions = set()
        scenes = set()
        for node in self._nodes.values():
            state = node.progress
            witnessed.update(inspect_campaign(state, self.flow)["endings"])
            missions.update(state.completed)
            scenes.update(c["scene"] for c in state.story_history)
        return {"nodes": len(self._nodes), "missions_completed_in_preview": sorted(missions),
                "scenes_chosen_in_preview": sorted(scenes),
                "endings_witnessed": sorted(witnessed),
                "endings_not_witnessed": sorted(
                    set(self.flow.get("endings", {})) - witnessed),
                "symbolic_only": True}
