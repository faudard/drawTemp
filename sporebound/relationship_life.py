"""R62.B.2: opt-in, deterministic relationships with R35 NPC identity/time.

One canonical GameSession owns inventory and social commands. The R35 world
owns NPC schedules and the calendar. This component only stores bounded
affinity and its replay-verifiable idempotent receipts. No wall clock, second
inventory or untrusted script evaluation.
"""
from __future__ import annotations

from copy import deepcopy
from .model import require

EXTENSION = "org.drawtemp.relationships"
VERSION = 1
MAX_NPCS = 64
MAX_GIFTS = 16
MAX_RECEIPTS = 2048
MAX_DAY = 2 ** 53 - 1
MIN_SCORE = -100
MAX_SCORE = 100


def _id(value):
    return (type(value) is str and 1 <= len(value) <= 64 and
            all(char.isascii() and (char.isalnum() or char in "_-")
                for char in value))


def _int(value, low, high):
    return type(value) is int and low <= value <= high


def validate_relationships(spec, npc_ids, item_ids, *, npc_activities=None):
    """Reject unbound NPCs, gifts, duplicates and invalid daily gain."""
    require(type(spec) is dict and set(spec) == {"version", "relationships"}
            and type(spec["version"]) is int and spec["version"] == VERSION
            and type(spec["relationships"]) is list
            and len(spec["relationships"]) <= MAX_NPCS,
            "R62 malformed relationship catalogue")
    used = set()
    for row in spec["relationships"]:
        require(type(row) is dict and set(row) ==
                {"npc", "initial", "talk_gain", "talk_activity", "gifts"}
                and _id(row["npc"]) and row["npc"] in npc_ids
                and row["npc"] not in used
                and _int(row["initial"], MIN_SCORE, MAX_SCORE)
                and _int(row["talk_gain"], 0, 20)
                and _id(row["talk_activity"])
                and type(row["gifts"]) is list and len(row["gifts"]) <= MAX_GIFTS,
                "R62 invalid social NPC, gain or activity")
        if row["talk_activity"] != "any" and npc_activities is not None:
            require(row["talk_activity"] in npc_activities.get(row["npc"], set()),
                    "R62 social activity is absent from R35 NPC schedule")
        used.add(row["npc"])
        items = set()
        for gift in row["gifts"]:
            require(type(gift) is dict and set(gift) == {"item", "gain"}
                    and _id(gift["item"]) and gift["item"] in item_ids
                    and gift["item"] not in items and _int(gift["gain"], -20, 20),
                    "R62 invalid or repeated social gift")
            items.add(gift["item"])
    return deepcopy(spec)


class RelationshipLife:
    """Bounded per-NPC affinity; reconstruct every score by ordered replay."""

    def __init__(self, spec, npc_ids, item_ids, *, npc_activities=None):
        self.npc_ids = frozenset(npc_ids)
        self.item_ids = frozenset(item_ids)
        self.npc_activities = deepcopy(npc_activities)
        self.spec = validate_relationships(
            spec, npc_ids, item_ids, npc_activities=npc_activities)
        self.definitions = {row["npc"]: row for row in self.spec["relationships"]}
        self.day = 0
        self.scores = {key: row["initial"] for key, row in self.definitions.items()}
        self.last_actions = {key: {"talk": -1, "gift": -1}
                             for key in self.definitions}
        self.journal = []
        self.receipts = {}

    def sync(self, day):
        require(_int(day, self.day, MAX_DAY), "R62 social day cannot go backwards")
        self.day = day

    def view(self, npc=None):
        require(npc is None or npc in self.definitions, "R62 unknown social NPC")
        keys = [npc] if npc is not None else sorted(self.definitions)
        rows = {}
        for key in keys:
            actions = self.last_actions[key]
            rows[key] = {
                "score": self.scores[key],
                "last_talk_day": actions["talk"],
                "last_gift_day": actions["gift"],
                "can_talk_today": actions["talk"] != self.day,
                "can_gift_today": actions["gift"] != self.day,
            }
        return {"version": VERSION, "day": self.day, "relationships": rows}

    def command(self, kind, npc, receipt_id, *, item=None):
        """Return item debit for gift, or None for a duplicate receipt.

        The caller owns the atomic Campaign inventory update. The caller also
        enforces current scene and R35 activity before the first execution.
        """
        require(kind in ("talk", "gift") and _id(npc) and _id(receipt_id)
                and (item is None if kind == "talk" else _id(item)),
                "R62 invalid social command")
        previous = self.receipts.get(receipt_id)
        if previous is not None:
            require(previous["kind"] == kind and previous["npc"] == npc
                    and previous.get("item") == item,
                    "R62 social receipt reused for a different action")
            return None
        require(npc in self.definitions and len(self.journal) < MAX_RECEIPTS,
                "R62 unknown NPC or social receipt budget exhausted")
        require(self.last_actions[npc][kind] != self.day,
                "R62 social action already completed today")
        row = self.definitions[npc]
        if kind == "talk":
            gain = row["talk_gain"]
        else:
            gift = next((gift for gift in row["gifts"] if gift["item"] == item), None)
            require(gift is not None, "R62 this NPC does not accept this gift")
            gain = gift["gain"]
        receipt = {"kind": kind, "npc": npc, "id": receipt_id, "day": self.day}
        if item is not None:
            receipt["item"] = item
        self.scores[npc] = max(MIN_SCORE, min(MAX_SCORE, self.scores[npc] + gain))
        self.last_actions[npc][kind] = self.day
        self.journal.append(receipt)
        self.receipts[receipt_id] = receipt
        return (item, -1) if item is not None else ("", 0)

    def snapshot(self):
        return {"version": VERSION, "day": self.day,
                "scores": deepcopy(self.scores),
                "last_actions": deepcopy(self.last_actions),
                "journal": deepcopy(self.journal)}

    def restore(self, data):
        require(type(data) is dict and set(data) ==
                {"version", "day", "scores", "last_actions", "journal"}
                and type(data["version"]) is int and data["version"] == VERSION
                and _int(data["day"], 0, MAX_DAY)
                and type(data["journal"]) is list
                and len(data["journal"]) <= MAX_RECEIPTS,
                "R62 malformed relationship checkpoint")
        replay = RelationshipLife(
            self.spec, self.npc_ids, self.item_ids,
            npc_activities=self.npc_activities)
        for receipt in data["journal"]:
            require(type(receipt) is dict
                    and set(receipt) == ({"kind", "npc", "id", "day", "item"}
                                         if receipt.get("kind") == "gift"
                                         else {"kind", "npc", "id", "day"})
                    and _id(receipt["id"])
                    and _int(receipt["day"], replay.day, data["day"])
                    and receipt["id"] not in replay.receipts,
                    "R62 malformed or duplicate social receipt")
            replay.sync(receipt["day"])
            replay.command(receipt["kind"], receipt["npc"], receipt["id"],
                           item=receipt.get("item"))
        replay.sync(data["day"])
        require(replay.snapshot() == data,
                "R62 relationship state disagrees with deterministic replay")
        self.day, self.scores, self.last_actions = (
            replay.day, replay.scores, replay.last_actions)
        self.journal, self.receipts = replay.journal, replay.receipts


__all__ = ["EXTENSION", "RelationshipLife", "validate_relationships"]
