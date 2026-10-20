"""R63.A — opt-in deterministic Survival & Crafting for GameSession.

Campaign owns the only inventory. This component owns needs, node stock, tool
wear and an ordered replay-verified journal; no CT, wall-clock or RNG changes.
"""
from __future__ import annotations

from copy import deepcopy
from .model import require

EXTENSION = "org.drawtemp.survival"
VERSION = 1
MAX_QUANTITY = 1_000_000
MAX_TICK = 1_000_000
MAX_STEP = 256
MAX_JOURNAL = 512


def _id(v):
    return type(v) is str and 1 <= len(v) <= 64 and all(
        c.isascii() and (c.isalnum() or c in "_-") for c in v)


def _int(v, lo, hi):
    return type(v) is int and lo <= v <= hi


def _materials(rows, items):
    require(type(rows) is dict and 1 <= len(rows) <= 8,
            "Survival material map must contain 1..8 items")
    for item, count in rows.items():
        require(_id(item) and item in items and _int(count, 1, 99),
                "Unknown or invalid survival item quantity")


def validate_survival(spec, scenes, *, exploration=None):
    """Fail closed on schema, references, bounds and self-crafting."""
    require(type(spec) is dict and set(spec) == {
        "version", "needs", "items", "tools", "nodes", "recipes", "shelters", "foods"},
        "Malformed R63 survival schema")
    require(type(spec["version"]) is int and spec["version"] == VERSION,
            "Unsupported R63 version; explicit migration required")
    needs = spec["needs"]
    require(type(needs) is dict and set(needs) == {
        "energy", "hunger", "temperature", "energy_drain", "hunger_drain", "cold_drain"}
        and all(_int(needs[k], 0, 100) for k in (
            "energy", "hunger", "temperature"))
        and all(_int(needs[k], 0, 10) for k in (
            "energy_drain", "hunger_drain", "cold_drain")),
        "Malformed survival needs")
    require(type(spec["items"]) is list and 1 <= len(spec["items"]) <= 64,
            "Survival requires 1..64 items")
    items = set()
    for item in spec["items"]:
        require(_id(item) and item not in items, "Duplicate/invalid survival item")
        items.add(item)
    require(type(spec["tools"]) is list and len(spec["tools"]) <= 16,
            "Too many survival tools")
    tools = set()
    for row in spec["tools"]:
        require(type(row) is dict and set(row) == {"id", "durability"}
                and _id(row["id"]) and row["id"] in items
                and row["id"] not in tools and _int(row["durability"], 1, 1000),
                "Invalid survival tool")
        tools.add(row["id"])
    def check_position(row):
        if "pos" not in row:
            return
        pos = row["pos"]
        require(type(pos) is list and len(pos) == 2
                and all(_int(n, 0, 1_000_000) for n in pos),
                "Survival placement must be a two-integer grid cell")
        if exploration is not None:
            scene = exploration.get(row["scene"])
            require(type(scene) is dict
                    and _int(scene.get("width"), 1, 1_000_000)
                    and _int(scene.get("height"), 1, 1_000_000)
                    and pos[0] < scene["width"] and pos[1] < scene["height"]
                    and pos not in scene.get("blocked", []),
                    "Survival placement outside map or on blocked cell")

    require(type(spec["nodes"]) is list and len(spec["nodes"]) <= 128,
            "Too many harvest nodes")
    nodes = set()
    for row in spec["nodes"]:
        require(type(row) is dict and
            {"id", "scene", "item", "stock", "yield", "tool", "wear", "energy_cost", "cold"} <= set(row)
            <= {"id", "scene", "item", "stock", "yield", "tool", "wear", "energy_cost", "cold", "pos"}
            and _id(row["id"]) and row["id"] not in nodes
            and type(row["scene"]) is str and row["scene"] in scenes
            and type(row["item"]) is str and row["item"] in items
            and (row["tool"] is None
                 or (type(row["tool"]) is str and row["tool"] in tools))
            and _int(row["stock"], 1, MAX_QUANTITY)
            and _int(row["yield"], 1, 99) and row["yield"] <= row["stock"]
            and _int(row["wear"], 0, 100)
            and (row["tool"] is not None or row["wear"] == 0)
            and _int(row["energy_cost"], 1, 100)
            and _int(row["cold"], 0, 100),
            "Invalid survival harvest node")
        check_position(row)
        nodes.add(row["id"])
    require(type(spec["recipes"]) is list and len(spec["recipes"]) <= 128,
            "Too many survival recipes")
    recipes = set()
    for row in spec["recipes"]:
        require(type(row) is dict and set(row) == {
            "id", "inputs", "outputs", "energy_cost"}
            and _id(row["id"]) and row["id"] not in recipes
            and _int(row["energy_cost"], 1, 100),
            "Invalid survival recipe")
        _materials(row["inputs"], items)
        _materials(row["outputs"], items)
        require(not (set(row["inputs"]) & set(row["outputs"])),
                "Crafting may not consume and produce the same item")
        recipes.add(row["id"])
    # Forbid transmutation cycles; finite nodes are the only material sources.
    # This keeps crafting acyclic and prevents recipe-driven item duplication.
    edges = {name: set() for name in items}
    for recipe in spec["recipes"]:
        for source in recipe["inputs"]:
            edges[source].update(recipe["outputs"])
    visiting, visited = set(), set()

    def visit(item):
        require(item not in visiting, "Cyclic survival crafting graph")
        if item in visited:
            return
        visiting.add(item)
        for target in sorted(edges[item]):
            visit(target)
        visiting.remove(item)
        visited.add(item)

    for item in sorted(items):
        visit(item)
    require(type(spec["foods"]) is list and len(spec["foods"]) <= 16,
            "Too many survival foods")
    food_items = set()
    for row in spec["foods"]:
        require(type(row) is dict and set(row) == {"item", "nutrition"}
                and _id(row["item"]) and row["item"] in items
                and row["item"] not in food_items and _int(row["nutrition"], 1, 100),
                "Invalid survival food")
        food_items.add(row["item"])
    require(type(spec["shelters"]) is list and len(spec["shelters"]) <= 32,
            "Too many shelters")
    shelters = set()
    for row in spec["shelters"]:
        require(type(row) is dict and
            {"id", "scene", "fuel", "energy_restore", "warmth"} <= set(row)
            <= {"id", "scene", "fuel", "energy_restore", "warmth", "pos"}
            and _id(row["id"]) and row["id"] not in shelters
            and type(row["scene"]) is str and row["scene"] in scenes
            and _int(row["energy_restore"], 1, 100)
            and _int(row["warmth"], 0, 100),
            "Invalid survival shelter")
        _materials(row["fuel"], items)
        check_position(row)
        shelters.add(row["id"])
    return deepcopy(spec)


class SurvivalRuntime:
    """Integer-time survival with atomic canonical inventory transfers."""

    def __init__(self, spec, scenes, *, exploration=None):
        self.spec = validate_survival(spec, scenes, exploration=exploration)
        self.scenes = frozenset(scenes)
        self.exploration = deepcopy(exploration) if exploration is not None else None
        self.nodes = {row["id"]: row for row in self.spec["nodes"]}
        self.recipes = {row["id"]: row for row in self.spec["recipes"]}
        self.shelters = {row["id"]: row for row in self.spec["shelters"]}
        self.foods = {row["item"]: row for row in self.spec["foods"]}
        self.tick = 0
        self.needs = {k: self.spec["needs"][k] for k in (
            "energy", "hunger", "temperature")}
        self.stock = {key: row["stock"] for key, row in self.nodes.items()}
        self.durability = {row["id"]: row["durability"]
                           for row in self.spec["tools"]}
        self.journal = []
        self.receipts = {}

    def _room(self, kind):
        if kind == "advance" and self.journal and self.journal[-1]["kind"] == "advance":
            return
        require(len(self.journal) < MAX_JOURNAL, "Survival journal exhausted")

    def _advance(self, ticks):
        require(_int(ticks, 1, MAX_STEP) and self.tick + ticks <= MAX_TICK,
                "Invalid R63 tick advance")
        self._room("advance")
        rates = self.spec["needs"]
        temperature = self.needs["temperature"]
        cold = rates["cold_drain"]
        # Closed-form cold exposure: this matches exactly N repeated one-tick
        # updates and avoids per-frame loops in large deterministic fast-forward.
        if cold == 0:
            exposure = ticks if temperature <= 20 else 0
        else:
            first_exposure = max(1, (max(0, temperature - 20) + cold - 1) // cold)
            exposure = max(0, ticks - first_exposure + 1)
        self.needs["temperature"] = max(0, temperature - ticks * cold)
        self.needs["hunger"] = max(0, self.needs["hunger"] - ticks * rates["hunger_drain"])
        self.needs["energy"] = max(
            0, self.needs["energy"] - ticks * rates["energy_drain"] - exposure)
        self.tick += ticks
        if self.journal and self.journal[-1]["kind"] == "advance":
            self.journal[-1]["ticks"] += ticks
        else:
            self.journal.append({"kind": "advance", "ticks": ticks})

    def advance(self, ticks=1):
        self._advance(ticks)
        return self.snapshot()

    def _transfer(self, inventory, debits, credits):
        changes = {}
        for item in set(debits) | set(credits):
            current = inventory.get(item, 0)
            require(_int(current, 0, MAX_QUANTITY), "Invalid campaign item count")
            value = current - debits.get(item, 0) + credits.get(item, 0)
            require(_int(value, 0, MAX_QUANTITY),
                    "Insufficient resources or inventory capacity exceeded")
            changes[item] = value
        return changes

    def _command(self, kind, entry_id, transaction_id, scene, inventory, *, replay=False):
        require(_id(transaction_id) and _id(entry_id)
                and type(scene) is str and scene in self.scenes,
                "Invalid survival command")
        previous = self.receipts.get(transaction_id)
        if previous is not None:
            require(previous == (kind, entry_id, scene),
                    "Survival transaction ID reused for a different command")
            return False
        self._room(kind)
        collection = {"gather": self.nodes, "craft": self.recipes,
                      "rest": self.shelters, "eat": self.foods}[kind]
        row = collection.get(entry_id)
        require(row is not None, "Unknown survival command target")
        require(kind in ("craft", "eat") or scene == row["scene"],
                "Survival action cannot execute in this scene")
        debit, credit = {}, {}
        cost = 0
        if kind == "gather":
            require(self.stock[entry_id] >= row["yield"], "Harvest node depleted")
            cost = row["energy_cost"]
            credit = {row["item"]: row["yield"]}
            tool = row["tool"]
            if tool is not None:
                require(self.durability[tool] >= row["wear"], "Tool is worn out")
                if not replay:
                    require(_int(inventory.get(tool, 0), 1, MAX_QUANTITY),
                            "Required tool not in campaign inventory")
        elif kind == "craft":
            cost = row["energy_cost"]
            debit, credit = row["inputs"], row["outputs"]
        elif kind == "rest":
            debit = row["fuel"]
        else:
            debit = {row["item"]: 1}
        require(self.needs["energy"] >= cost
                and (kind in ("rest", "eat") or self.needs["hunger"] > 0),
                "Survival needs too low for this action")
        if not replay:
            changes = self._transfer(inventory, debit, credit)
        # Replay verifies component-owned state; Campaign inventory is not
        # duplicated here. It stays under the canonical GameSession checksum.
        if kind == "gather":
            self.stock[entry_id] -= row["yield"]
            if row["tool"] is not None:
                self.durability[row["tool"]] -= row["wear"]
            self.needs["temperature"] = max(0, self.needs["temperature"] - row["cold"])
        elif kind == "rest":
            self.needs["energy"] = min(100, self.needs["energy"] + row["energy_restore"])
            self.needs["temperature"] = min(100, self.needs["temperature"] + row["warmth"])
        elif kind == "eat":
            self.needs["hunger"] = min(100, self.needs["hunger"] + row["nutrition"])
        self.needs["energy"] -= cost
        if not replay:
            inventory.update(changes)
        self.receipts[transaction_id] = (kind, entry_id, scene)
        self.journal.append({"kind": kind, "id": entry_id,
                             "transaction": transaction_id,
                             "scene": scene, "tick": self.tick})
        return True

    def gather(self, progress, scene, node_id, transaction_id):
        return self._command("gather", node_id, transaction_id,
                             scene, progress.inventory)

    def craft(self, progress, scene, recipe_id, transaction_id):
        return self._command("craft", recipe_id, transaction_id,
                             scene, progress.inventory)

    def rest(self, progress, scene, shelter_id, transaction_id):
        return self._command("rest", shelter_id, transaction_id,
                             scene, progress.inventory)

    def eat(self, progress, scene, food_id, transaction_id):
        return self._command("eat", food_id, transaction_id,
                             scene, progress.inventory)

    def snapshot(self):
        return {"version": VERSION, "tick": self.tick,
                "needs": deepcopy(self.needs), "stock": deepcopy(self.stock),
                "durability": deepcopy(self.durability),
                "journal": deepcopy(self.journal)}

    def restore(self, snapshot):
        require(type(snapshot) is dict and set(snapshot) == {
            "version", "tick", "needs", "stock", "durability", "journal"}
            and type(snapshot["version"]) is int and snapshot["version"] == VERSION
            and type(snapshot["journal"]) is list
            and len(snapshot["journal"]) <= MAX_JOURNAL,
            "Malformed R63 checkpoint")
        replay = SurvivalRuntime(self.spec, self.scenes, exploration=self.exploration)
        for event in snapshot["journal"]:
            require(type(event) is dict and "kind" in event,
                    "Invalid survival replay event")
            if event["kind"] == "advance":
                require(set(event) == {"kind", "ticks"}
                        and _int(event["ticks"], 1, MAX_TICK),
                        "Invalid survival tick receipt")
                ticks = event["ticks"]
                while ticks:
                    step = min(MAX_STEP, ticks)
                    replay._advance(step)
                    ticks -= step
            else:
                require(set(event) == {"kind", "id", "transaction", "scene", "tick"}
                        and event["kind"] in ("gather", "craft", "rest", "eat")
                        and type(event["tick"]) is int
                        and event["tick"] == replay.tick,
                        "Malformed survival operation receipt")
                require(replay._command(event["kind"], event["id"],
                         event["transaction"], event["scene"], {}, replay=True),
                        "Duplicate survival transaction receipt")
        require(snapshot == replay.snapshot(), "R63 checkpoint diverges from replay")
        self.tick, self.needs = replay.tick, replay.needs
        self.stock, self.durability = replay.stock, replay.durability
        self.journal, self.receipts = replay.journal, replay.receipts


__all__ = ["EXTENSION", "VERSION", "SurvivalRuntime", "validate_survival"]
