"""R37.C — visual Behavior Tree draft over canonical R1 AuthoringSession.

The draft is never authoritative. Every mutation is a detached, validated
tree, and Apply writes one atomic GameProject extension transaction with Undo.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.authoring import AuthoringSession
from drawtemp.sdk.behavior_tree import validate_behavior_tree
from drawtemp.sdk.ai_decision import AIDecisionError
from sporebound.advanced_ai import EXTENSION


class BehaviorTreeDraft:
    def __init__(self, session: AuthoringSession, actor_id):
        if not isinstance(session, AuthoringSession):
            raise TypeError("Expected active AuthoringSession")
        project = session.snapshot().to_dict()["project"]
        agents = project.get("extensions", {}).get(EXTENSION, {}).get(
            "data", {}).get("agents", [])
        agent = next((row for row in agents if row["id"] == actor_id), None)
        if agent is None:
            raise ValueError("Unknown R37 actor: " + str(actor_id))
        self.session = session
        self.actor_id = actor_id
        self.source_revision = session.revision
        self.tree = deepcopy(agent.get("tree", {
            "schema_version": 1, "root": "root",
            "nodes": [
                {"id": "root", "kind": "selector", "children": ["wait1"]},
                {"id": "wait1", "kind": "action", "action": "wait"},
            ],
        }))
        validate_behavior_tree(self.tree)

    def document(self):
        return deepcopy(self.tree)

    def _edit(self, mutate):
        candidate = deepcopy(self.tree)
        mutate(candidate)
        validate_behavior_tree(candidate)
        self.tree = candidate
        return self.document()

    def _id(self, tree, prefix):
        used = {node["id"] for node in tree["nodes"]}
        for index in range(1, 65):
            identifier = prefix + str(index)
            if identifier not in used:
                return identifier
        raise ValueError("Node identifier budget exceeded")

    def add(self, parent, kind, *, fact="same_scene", equals=True,
            action="wait"):
        """Append a child to a sequence or selector without an invalid gap."""
        if kind not in ("condition", "action", "sequence", "selector"):
            raise ValueError("Unsupported authored behavior node")
        added = []
        def change(tree):
            ancestor = next((n for n in tree["nodes"] if n["id"] == parent), None)
            if ancestor is None or ancestor["kind"] not in ("selector", "sequence"):
                raise ValueError("Select a sequence or selector parent")
            if len(ancestor["children"]) >= 16 or len(tree["nodes"]) + (
                    2 if kind in ("selector", "sequence") else 1) > 64:
                raise ValueError("Behavior Tree budget exhausted")
            node_id = self._id(tree, kind)
            if kind in ("selector", "sequence"):
                leaf_id = self._id(
                    {"nodes": [*tree["nodes"], {"id": node_id}]}, "wait")
                node = {"id": node_id, "kind": kind, "children": [leaf_id]}
                tree["nodes"].append({"id": leaf_id, "kind": "action",
                                      "action": "wait"})
            elif kind == "condition":
                node = {"id": node_id, "kind": kind,
                        "fact": fact, "equals": equals}
            else:
                node = {"id": node_id, "kind": kind, "action": action}
            ancestor["children"].append(node_id)
            tree["nodes"].append(node)
            added.append(node_id)
        self._edit(change)
        return added[0]

    def edit(self, node_id, **properties):
        """Only leaf properties are editable; structural edits use add/remove."""
        def change(tree):
            node = next((n for n in tree["nodes"] if n["id"] == node_id), None)
            if node is None or node["kind"] not in ("condition", "action"):
                raise ValueError("Select an action or condition")
            if set(properties) != ({"action"} if node["kind"] == "action"
                                   else {"fact", "equals"}):
                raise ValueError("Incomplete behavior leaf properties")
            node.update(deepcopy(properties))
        return self._edit(change)

    def wrap_inverter(self, node_id):
        """Wrap any subtree in a single-child decorator with one undoable edit."""
        result = []
        def change(tree):
            node = next((n for n in tree["nodes"] if n["id"] == node_id), None)
            if node is None:
                raise ValueError("Unknown subtree")
            if len(tree["nodes"]) >= 64:
                raise ValueError("Behavior Tree budget exhausted")
            wrapper_id = self._id(tree, "invert")
            parent = next((n for n in tree["nodes"]
                           if node_id in n.get("children", [])
                           or n.get("child") == node_id), None)
            if parent is None:
                tree["root"] = wrapper_id
            elif "children" in parent:
                index = parent["children"].index(node_id)
                parent["children"][index] = wrapper_id
            else:
                parent["child"] = wrapper_id
            tree["nodes"].append({
                "id": wrapper_id, "kind": "decorator",
                "op": "invert", "child": node_id})
            result.append(wrapper_id)
        self._edit(change)
        return result[0]

    def remove(self, node_id):
        def change(tree):
            if node_id == tree["root"]:
                raise ValueError("Cannot delete the root")
            parent = next((node for node in tree["nodes"]
                           if node_id in node.get("children", [])
                           or node.get("child") == node_id), None)
            if parent is None or parent["kind"] not in ("sequence", "selector"):
                raise ValueError("Cannot delete the only decorator child")
            if len(parent["children"]) == 1:
                raise ValueError("A composite cannot have zero children")
            to_remove = {node_id}
            while True:
                extra = {child for node in tree["nodes"]
                         if node["id"] in to_remove
                         for child in (node.get("children", [])
                                       + ([node["child"]] if "child" in node else []))}
                if extra <= to_remove:
                    break
                to_remove |= extra
            tree["nodes"] = [n for n in tree["nodes"]
                             if n["id"] not in to_remove]
            parent["children"].remove(node_id)
        return self._edit(change)

    def reorder(self, node_id, offset):
        if offset not in (-1, 1):
            raise ValueError("Expected adjacent reordering")
        def change(tree):
            parent = next((node for node in tree["nodes"]
                           if node_id in node.get("children", [])), None)
            if parent is None:
                raise ValueError("Node has no ordered composite parent")
            items = parent["children"]
            index = items.index(node_id)
            new_index = index + offset
            if not 0 <= new_index < len(items):
                raise ValueError("Cannot reorder beyond composite boundary")
            items[index], items[new_index] = items[new_index], items[index]
        return self._edit(change)

    def prepare(self):
        if self.source_revision != self.session.revision:
            raise ValueError("Stale AI editor draft; reload current project")
        validated = validate_behavior_tree(self.tree)
        actor_id = self.actor_id

        def change(project):
            extension = project.get("extensions", {}).get(EXTENSION)
            if extension is None:
                raise ValueError("R37 AI extension was removed")
            agent = next((a for a in extension["data"]["agents"]
                          if a["id"] == actor_id), None)
            if agent is None:
                raise ValueError("R37 AI actor was removed")
            agent.pop("policies", None)
            agent["tree"] = deepcopy(validated)
            return project

        return self.session.preview_project(change, kind="r37.behavior-tree")

    def apply(self):
        plan = self.prepare()
        transition = self.session.apply(plan)
        self.source_revision = self.session.revision
        return transition
