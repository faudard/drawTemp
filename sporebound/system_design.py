"""R55.A: deterministic, opt-in system economy owned by GameSession.

Authoring lives in GameProject.extensions. Runtime stock and the bounded,
ordered operation journal are the only system-owned mutable state. Player
inventory, gold and quest flags remain on the canonical Campaign progress.
No code evaluation, wall-clock scheduling, or implicit resource generation.
"""
from __future__ import annotations

from copy import deepcopy

from .model import require

EXTENSION = "org.drawtemp.systems"
VERSION = 1
MAX_STOCK = 1_000_000
MAX_TICKS = 65_536
MAX_ADVANCE = 256
MAX_COMMANDS = 512


def _id(value):
    return (type(value) is str and 1 <= len(value) <= 64
            and all(c.isascii() and (c.isalnum() or c in "_-") for c in value))


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _amounts(data, resources):
    require(type(data) is dict and 1 <= len(data) <= 16,
            "R55 recipe needs a nonempty bounded resource map")
    for key, value in data.items():
        require(_id(key) and key in resources and _integer(value, 1, 1000),
                "R55 recipe has an invalid typed resource amount")


def validate_systems(spec, scenes):
    """Fail closed on unknown schema/fields, unsafe cycles and unbounded work."""
    require(type(spec) is dict and set(spec) ==
            {"version", "resources", "producers", "merchants", "quests"},
            "Malformed R55 system graph")
    require(type(spec["version"]) is int and spec["version"] == VERSION,
            "Unsupported R55 system version; explicit migration required")
    resources = spec["resources"]
    producers = spec["producers"]
    merchants = spec["merchants"]
    quests = spec["quests"]
    require(type(resources) is list and 1 <= len(resources) <= 64
            and type(producers) is list and len(producers) <= 32
            and type(merchants) is list and len(merchants) <= 16
            and type(quests) is list and len(quests) <= 32,
            "R55 system graph exceeds authored budgets")
    known = {}
    for row in resources:
        require(type(row) is dict and set(row) == {"id", "initial", "capacity"}
                and _id(row["id"]) and row["id"] not in known
                and _integer(row["capacity"], 1, MAX_STOCK)
                and _integer(row["initial"], 0, row["capacity"]),
                "R55 resource needs a unique identity and bounded stock")
        known[row["id"]] = row
    used = set()
    edges = {name: set() for name in known}
    for row in producers:
        require(type(row) is dict and set(row) ==
                {"id", "inputs", "outputs", "interval"}
                and _id(row["id"]) and row["id"] not in used
                and _integer(row["interval"], 1, 256),
                "R55 producer has invalid identity or interval")
        used.add(row["id"])
        _amounts(row["inputs"], known)
        _amounts(row["outputs"], known)
        for source in row["inputs"]:
            edges[source].update(row["outputs"])
    # A cycle (including a self-loop) requires an explicit future contract;
    # rejecting it prevents free energy/ambiguous iterative tick resolution.
    visiting, visited = set(), set()

    def visit(name):
        require(name not in visiting, "R55 resource production cycle")
        if name in visited:
            return
        visiting.add(name)
        for target in sorted(edges[name]):
            visit(target)
        visiting.remove(name)
        visited.add(name)

    for name in sorted(known):
        visit(name)
    used.clear()
    for row in merchants:
        require(type(row) is dict and set(row) ==
                {"id", "resource", "scene", "buy_price", "sell_price"}
                and _id(row["id"]) and row["id"] not in used
                and _id(row["resource"]) and row["resource"] in known
                and type(row["scene"]) is str and row["scene"] in scenes
                and _integer(row["buy_price"], 0, MAX_STOCK)
                and _integer(row["sell_price"], 0, row["buy_price"]),
                "Invalid R55 merchant, scene or price")
        used.add(row["id"])
    used.clear()
    flags = set()
    for row in quests:
        require(type(row) is dict and set(row) ==
                {"id", "resource", "quantity", "flag"}
                and _id(row["id"]) and row["id"] not in used
                and _id(row["resource"]) and row["resource"] in known
                and _integer(row["quantity"], 1, 1000)
                and _id(row["flag"]) and row["flag"] not in flags,
                "Invalid R55 quest contract")
        used.add(row["id"])
        flags.add(row["flag"])
    return deepcopy(spec)


class SystemEconomy:
    """Authoritative session component; deterministic on integer ticks.

    Replay reconstructs exact stock from initial resources and the journal.
    Invalid or modified stock, producer order, duplicate receipts, stale schema,
    overflow and nonconserving operations are rejected before restore commits.
    """

    def __init__(self, spec, scenes):
        self.spec = validate_systems(spec, scenes)
        self.scenes = frozenset(scenes)
        self.producers = sorted(self.spec["producers"], key=lambda row: row["id"])
        self.merchants = {row["id"]: row for row in self.spec["merchants"]}
        self.quests = {row["id"]: row for row in self.spec["quests"]}
        self.resources = {row["id"]: row for row in self.spec["resources"]}
        self.stocks = {key: row["initial"] for key, row in self.resources.items()}
        self.tick = 0
        self.journal = []
        self.transaction_ids = set()
        self.fulfilled = set()

    def _room(self):
        require(len(self.journal) < MAX_COMMANDS, "R55 command journal is full")

    def _advance_core(self, ticks):
        require(_integer(ticks, 1, MAX_ADVANCE) and self.tick + ticks <= MAX_TICKS,
                "R55 tick advance exceeds deterministic budget")
        for t in range(self.tick + 1, self.tick + ticks + 1):
            for producer in self.producers:
                if t % producer["interval"]:
                    continue
                inputs, outputs = producer["inputs"], producer["outputs"]
                if not all(self.stocks[key] >= qty for key, qty in inputs.items()):
                    continue
                if not all(self.stocks[key] + qty <= self.resources[key]["capacity"]
                           for key, qty in outputs.items()):
                    continue
                for key, qty in inputs.items():
                    self.stocks[key] -= qty
                for key, qty in outputs.items():
                    self.stocks[key] += qty
        self.tick += ticks

    def advance(self, ticks=1):
        self._room()
        self._advance_core(ticks)
        self.journal.append({"kind": "advance", "ticks": ticks})
        return self.snapshot()

    def _trade_stock(self, merchant, action, quantity):
        key = merchant["resource"]
        new = self.stocks[key] + (quantity if action == "sell" else -quantity)
        require(0 <= new <= self.resources[key]["capacity"],
                "R55 trade exceeds available stock or capacity")
        return key, new

    def trade(self, progress, scene, merchant_id, action, quantity, transaction_id):
        """Atomic transfer against canonical Campaign inventory and gold."""
        require(_id(transaction_id) and _id(merchant_id)
                and action in ("buy", "sell") and _integer(quantity, 1, 99),
                "Invalid R55 trade command")
        previous = next((row for row in self.journal
                         if row["kind"] == "trade" and row["id"] == transaction_id), None)
        if previous is not None:
            require((previous["merchant"], previous["action"], previous["quantity"],
                     previous["scene"]) == (merchant_id, action, quantity, scene),
                    "R55 receipt reused for a different trade")
            return False
        self._room()
        merchant = self.merchants.get(merchant_id)
        require(merchant is not None and scene == merchant["scene"],
                "R55 merchant is unknown or off-scene")
        key, remaining = self._trade_stock(merchant, action, quantity)
        count = progress.inventory.get(key, 0)
        gold = progress.gold
        require(_integer(count, 0, MAX_STOCK) and _integer(gold, 0, MAX_STOCK),
                "Invalid canonical Campaign inventory/currency")
        price = merchant["buy_price"] if action == "buy" else merchant["sell_price"]
        total = price * quantity
        if action == "buy":
            require(gold >= total and count + quantity <= MAX_STOCK,
                    "Insufficient R55 funds or player inventory capacity")
            new_count, new_gold = count + quantity, gold - total
        else:
            require(count >= quantity and gold + total <= MAX_STOCK,
                    "Insufficient R55 items or player currency capacity")
            new_count, new_gold = count - quantity, gold + total
        # Commit only after *all* predicates succeed.
        self.stocks[key] = remaining
        progress.inventory[key] = new_count
        progress.gold = new_gold
        self.transaction_ids.add(transaction_id)
        self.journal.append({
            "kind": "trade", "id": transaction_id, "merchant": merchant_id,
            "action": action, "quantity": quantity, "scene": scene,
            "price": price, "tick": self.tick})
        return True

    def fulfill(self, progress, quest_id):
        """Deliver canonical inventory items; a story flag is the quest output."""
        require(_id(quest_id) and quest_id in self.quests, "Unknown R55 quest")
        if quest_id in self.fulfilled:
            return False
        self._room()
        row = self.quests[quest_id]
        key = row["resource"]
        count = progress.inventory.get(key, 0)
        require(_integer(count, 0, MAX_STOCK) and count >= row["quantity"]
                and progress.story_flags.get(row["flag"]) is not True,
                "R55 quest delivery is unavailable")
        progress.inventory[key] = count - row["quantity"]
        progress.story_flags[row["flag"]] = True
        self.fulfilled.add(quest_id)
        self.journal.append({"kind": "quest", "id": quest_id, "tick": self.tick})
        return True

    def snapshot(self):
        return {"version": VERSION, "tick": self.tick,
                "stocks": deepcopy(self.stocks), "journal": deepcopy(self.journal)}

    def restore(self, checkpoint):
        """Re-execute bounded commands before accepting any persisted state."""
        require(type(checkpoint) is dict and set(checkpoint) ==
                {"version", "tick", "stocks", "journal"}
                and type(checkpoint["version"]) is int
                and checkpoint["version"] == VERSION
                and type(checkpoint["journal"]) is list
                and len(checkpoint["journal"]) <= MAX_COMMANDS,
                "Malformed R55 checkpoint")
        require(_integer(checkpoint["tick"], 0, MAX_TICKS)
                and type(checkpoint["stocks"]) is dict
                and set(checkpoint["stocks"]) == set(self.resources)
                and all(_integer(count, 0, self.resources[key]["capacity"])
                        for key, count in checkpoint["stocks"].items()),
                "Malformed or non-integer R55 persisted stock")
        replay = SystemEconomy(self.spec, self.scenes)
        for command in checkpoint["journal"]:
            require(type(command) is dict, "Malformed R55 operation journal")
            kind = command.get("kind")
            if kind == "advance":
                require(set(command) == {"kind", "ticks"},
                        "Malformed R55 tick receipt")
                replay.advance(command["ticks"])
            elif kind == "trade":
                require(set(command) ==
                        {"kind", "id", "merchant", "action", "quantity",
                         "scene", "price", "tick"}, "Malformed R55 trade receipt")
                mid, transaction_id = command["merchant"], command["id"]
                require(_id(mid), "Invalid R55 merchant receipt ID")
                merchant = replay.merchants.get(mid)
                require(_id(transaction_id) and transaction_id not in replay.transaction_ids
                        and merchant is not None and command["scene"] == merchant["scene"]
                        and command["action"] in ("buy", "sell")
                        and _integer(command["quantity"], 1, 99)
                        and command["tick"] == replay.tick,
                        "Invalid or duplicate R55 trade receipt")
                price = (merchant["buy_price"] if command["action"] == "buy"
                         else merchant["sell_price"])
                require(command["price"] == price and type(command["price"]) is int,
                        "R55 trade receipt price differs from contract")
                key, result = replay._trade_stock(
                    merchant, command["action"], command["quantity"])
                replay._room()
                replay.stocks[key] = result
                replay.transaction_ids.add(transaction_id)
                replay.journal.append(deepcopy(command))
            elif kind == "quest":
                require(set(command) == {"kind", "id", "tick"}
                        and _id(command["id"]) and command["id"] in replay.quests
                        and command["id"] not in replay.fulfilled
                        and command["tick"] == replay.tick,
                        "Invalid or duplicate R55 quest receipt")
                replay._room()
                replay.fulfilled.add(command["id"])
                replay.journal.append(deepcopy(command))
            else:
                require(False, "Unknown R55 operation kind")
        require(checkpoint == replay.snapshot(),
                "R55 checkpoint diverges from replayed resource conservation")
        self.tick = replay.tick
        self.stocks = replay.stocks
        self.journal = replay.journal
        self.transaction_ids = replay.transaction_ids
        self.fulfilled = replay.fulfilled

    def preview(self, ticks):
        """Detached flow forecast, never mutates the live runtime."""
        clone = SystemEconomy(self.spec, self.scenes)
        clone.restore(self.snapshot())
        clone.advance(ticks)
        return clone.snapshot()


__all__ = ["EXTENSION", "SystemEconomy", "validate_systems"]
