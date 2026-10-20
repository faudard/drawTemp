"""R62.A: opt-in, deterministic farming lifecycle on the R35 world calendar.

The GameSession owns canonical inventory and the R35 LivingWorld owns time.
This component owns only plot/animal decisions and a replay-checked receipt
journal. No UI clock, off-scene ticking, secondary inventory or RNG state.
"""
from __future__ import annotations

from copy import deepcopy

from .model import require

EXTENSION = "org.drawtemp.farming"
VERSION = 1
SEASONS = ("spring", "summer", "autumn", "winter")
SOILS = ("loam", "clay", "sand")
MAX_DAYS = 2 ** 53 - 1
MAX_RECEIPTS = 1024
MAX_ITEM_QUANTITY = 1_000_000


def _id(value):
    return (type(value) is str and 1 <= len(value) <= 64
            and all(ch.isascii() and (ch.isalnum() or ch in "_-")
                    for ch in value))


def _int(value, lo, hi):
    return type(value) is int and lo <= value <= hi


def validate_farming(spec, scene_ids, item_ids):
    """Reject unbounded, unknown or non-canonical farming authoring."""
    require(type(spec) is dict and set(spec) ==
            {"version", "seed", "season_days", "weather", "plots", "crops", "animals"},
            "R62 invalid farming schema")
    require(type(spec["version"]) is int and spec["version"] == VERSION
            and _int(spec["seed"], 0, 2 ** 31 - 1)
            and _int(spec["season_days"], 2, 120)
            and type(spec["weather"]) is bool,
            "R62 invalid calendar/weather settings")
    plots, crops, animals = spec["plots"], spec["crops"], spec["animals"]
    require(type(plots) is list and len(plots) <= 128
            and type(crops) is list and len(crops) <= 64
            and type(animals) is list and len(animals) <= 64,
            "R62 farming authoring exceeds budgets")
    used = set()
    for row in plots:
        require(type(row) is dict and set(row) == {"id", "scene", "soil"}
                and _id(row["id"]) and row["id"] not in used
                and type(row["scene"]) is str and row["scene"] in scene_ids
                and type(row["soil"]) is str and row["soil"] in SOILS,
                "R62 invalid plot or scene")
        used.add(row["id"])
    used.clear()
    for row in crops:
        require(type(row) is dict and set(row) ==
                {"id", "seed_item", "yield_item", "yield_quantity",
                 "grow_days", "soils", "seasons"}
                and _id(row["id"]) and row["id"] not in used
                and _id(row["seed_item"]) and row["seed_item"] in item_ids
                and _id(row["yield_item"]) and row["yield_item"] in item_ids
                and _int(row["yield_quantity"], 1, 99)
                and _int(row["grow_days"], 1, 120)
                and type(row["soils"]) is list and bool(row["soils"])
                and all(type(value) is str for value in row["soils"])
                and len(row["soils"]) == len(set(row["soils"]))
                and set(row["soils"]) <= set(SOILS)
                and type(row["seasons"]) is list and bool(row["seasons"])
                and all(type(value) is str for value in row["seasons"])
                and len(row["seasons"]) == len(set(row["seasons"]))
                and set(row["seasons"]) <= set(SEASONS),
                "R62 invalid crop or canonical item reference")
        used.add(row["id"])
    used.clear()
    for row in animals:
        require(type(row) is dict and set(row) ==
                {"id", "scene", "feed_item", "yield_item",
                 "yield_quantity", "interval_days"}
                and _id(row["id"]) and row["id"] not in used
                and type(row["scene"]) is str and row["scene"] in scene_ids
                and _id(row["feed_item"]) and row["feed_item"] in item_ids
                and _id(row["yield_item"]) and row["yield_item"] in item_ids
                and _int(row["yield_quantity"], 1, 99)
                and _int(row["interval_days"], 1, 120),
                "R62 invalid animal or canonical item reference")
        used.add(row["id"])
    return deepcopy(spec)


class FarmingLife:
    """Farm state projected from world day; replay-check every gameplay receipt.

    Calls to sync(day) model off-focus time without per-day work. A fixed seed
    derives optional weather, and never relies on Python's randomized hash().
    """

    def __init__(self, spec, scene_ids, item_ids):
        self.spec = validate_farming(spec, scene_ids, item_ids)
        self.scene_ids = frozenset(scene_ids)
        self.item_ids = frozenset(item_ids)
        self.plots = {row["id"]: row for row in self.spec["plots"]}
        self.crops = {row["id"]: row for row in self.spec["crops"]}
        self.animals = {row["id"]: row for row in self.spec["animals"]}
        self.day = 0
        self.planted = {key: None for key in self.plots}
        self.animal_state = {
            key: {"last_fed": -1, "last_collected": 0} for key in self.animals}
        self.journal = []
        self.receipts = {}

    def sync(self, day):
        require(_int(day, self.day, MAX_DAYS), "R62 world day moved backwards")
        self.day = day

    @property
    def season(self):
        return SEASONS[(self.day // self.spec["season_days"]) % len(SEASONS)]

    def weather(self, day=None):
        if not self.spec["weather"]:
            return None
        day = self.day if day is None else day
        require(_int(day, 0, MAX_DAYS), "R62 invalid weather day")
        # Integer arithmetic stable on all platforms, independent of focus.
        sample = (self.spec["seed"] * 1103515245 + day * 12345 + 1013904223) % 8
        return "rain" if sample < 3 else ("cloud" if sample < 5 else "sun")

    def view(self, scene=None):
        require(scene is None or scene in self.scene_ids,
                "R62 unknown farm scene")
        plots = {}
        for key, row in sorted(self.plots.items()):
            if scene is not None and row["scene"] != scene:
                continue
            state = self.planted[key]
            crop = self.crops[state["crop"]] if state is not None else None
            plots[key] = {
                "scene": row["scene"], "soil": row["soil"],
                "crop": state["crop"] if state else None,
                "ready": bool(state and self.day - state["day"] >= crop["grow_days"]),
                "planted_day": state["day"] if state else None,
            }
        animals = {}
        for key, row in sorted(self.animals.items()):
            if scene is not None and row["scene"] != scene:
                continue
            status = self.animal_state[key]
            animals[key] = {
                "scene": row["scene"], "hunger": min(3, self.day - status["last_fed"])
                if status["last_fed"] >= 0 else 3,
                "ready": (status["last_fed"] >= self.day - 1
                          and self.day - status["last_collected"] >= row["interval_days"]),
            }
        return {"version": VERSION, "day": self.day, "season": self.season,
                "weather": self.weather(), "plots": plots, "animals": animals}

    def _execute(self, kind, target, crop=None):
        """Domain-only command; GameSession performs Campaign inventory writes."""
        if kind == "plant":
            plot, authored = self.plots.get(target), self.crops.get(crop)
            require(plot is not None and authored is not None
                    and self.planted[target] is None
                    and plot["soil"] in authored["soils"]
                    and self.season in authored["seasons"], "R62 planting is not permitted")
            self.planted[target] = {"crop": crop, "day": self.day}
            return authored["seed_item"], -1
        if kind == "harvest":
            require(target in self.plots and self.planted[target] is not None,
                    "R62 plot has no growing crop")
            planted = self.planted[target]
            authored = self.crops[planted["crop"]]
            require(self.day - planted["day"] >= authored["grow_days"],
                    "R62 crop is not ready")
            self.planted[target] = None
            return authored["yield_item"], authored["yield_quantity"]
        require(target in self.animals, "R62 unknown animal")
        row, state = self.animals[target], self.animal_state[target]
        if kind == "feed":
            require(state["last_fed"] != self.day, "R62 animal was already fed today")
            state["last_fed"] = self.day
            return row["feed_item"], -1
        require(kind == "collect"
                and state["last_fed"] >= self.day - 1
                and self.day - state["last_collected"] >= row["interval_days"],
                "R62 animal is hungry or produce is not ready")
        state["last_collected"] = self.day
        return row["yield_item"], row["yield_quantity"]

    def command(self, kind, target, receipt_id, *, crop=None):
        require(kind in {"plant", "harvest", "feed", "collect"}
                and _id(target) and _id(receipt_id)
                and (kind == "plant") == (crop is not None)
                and (crop is None or _id(crop)), "R62 malformed farm command")
        row = {"kind": kind, "target": target, "id": receipt_id, "day": self.day}
        if crop is not None:
            row["crop"] = crop
        previous = self.receipts.get(receipt_id)
        if previous is not None:
            # Retry remains idempotent even after the world's day advances.
            require(previous["kind"] == kind and previous["target"] == target
                    and previous.get("crop") == crop,
                    "R62 receipt reused for another command")
            return None
        require(len(self.journal) < MAX_RECEIPTS, "R62 receipt budget exceeded")
        # Safe because all domain preconditions are checked before the write.
        result = self._execute(kind, target, crop)
        self.journal.append(row)
        self.receipts[receipt_id] = row
        return result

    def snapshot(self):
        return {"version": VERSION, "day": self.day, "plots": deepcopy(self.planted),
                "animals": deepcopy(self.animal_state), "journal": deepcopy(self.journal)}

    def restore(self, data):
        require(type(data) is dict and set(data) ==
                {"version", "day", "plots", "animals", "journal"}
                and type(data["version"]) is int and data["version"] == VERSION
                and _int(data["day"], 0, MAX_DAYS)
                and type(data["journal"]) is list
                and len(data["journal"]) <= MAX_RECEIPTS,
                "R62 invalid farm checkpoint")
        replay = FarmingLife(self.spec, self.scene_ids, self.item_ids)
        for row in data["journal"]:
            require(type(row) is dict
                    and set(row) == ({"kind", "target", "id", "day", "crop"}
                                     if row.get("kind") == "plant"
                                     else {"kind", "target", "id", "day"})
                    and _int(row["day"], replay.day, data["day"]),
                    "R62 malformed farm receipt")
            replay.sync(row["day"])
            require(row["id"] not in replay.receipts, "R62 duplicate farm receipt")
            replay.command(row["kind"], row["target"], row["id"],
                           crop=row.get("crop"))
        replay.sync(data["day"])
        require(replay.snapshot() == data,
                "R62 farm checkpoint disagrees with deterministic replay")
        self.day = replay.day
        self.planted = replay.planted
        self.animal_state = replay.animal_state
        self.journal = replay.journal
        self.receipts = replay.receipts


__all__ = ["EXTENSION", "FarmingLife", "validate_farming"]
