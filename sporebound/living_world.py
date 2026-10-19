"""R35.A: deterministic, opt-in living-world clock and NPC schedules.

The canonical authoring source is GameProject.extensions["org.drawtemp.livingworld"].
NPC positions between schedule stops are NOT simulated; off-focus actors are
projected at authored stops. Rendering never drives the clock. No second world
database, wall-clock time, CT advance or mutable NPC copies are introduced.
"""
from __future__ import annotations

from copy import deepcopy

from .model import require

EXTENSION = "org.drawtemp.livingworld"
VERSION = 1
MAX_NPCS = 256
MAX_STOPS = 32
MAX_TICKS = 2 ** 53 - 1
MAX_ADVANCE = 1_000_000


def _identifier(value):
    return (type(value) is str and 1 <= len(value) <= 64
            and all(c.isascii() and (c.isalnum() or c in "_-")
                    for c in value))


def validate_living_world(spec, scene_ids):
    """Validate optional R35 authoring data against canonical scene identities."""
    require(type(spec) is dict and set(spec) ==
            {"version", "start_minute", "ticks_per_minute", "clock_policy", "npcs"},
            "Malformed living-world document")
    require(type(spec["version"]) is int and spec["version"] == VERSION,
            "Unsupported living-world version; explicit migration required")
    require(type(spec["start_minute"]) is int
            and 0 <= spec["start_minute"] < 1440,
            "Living-world start must be a minute in 0..1439")
    require(type(spec["ticks_per_minute"]) is int
            and 1 <= spec["ticks_per_minute"] <= 3600,
            "Living-world ticks_per_minute must be in 1..3600")
    require(spec["clock_policy"] == "exploration_only",
            "Only exploration_only living-world clock policy is supported")
    require(type(spec["npcs"]) is list and len(spec["npcs"]) <= MAX_NPCS,
            "Too many living-world NPCs")
    ids = set()
    for npc in spec["npcs"]:
        require(type(npc) is dict and set(npc) == {"id", "schedule"},
                "Living-world NPC requires id and schedule")
        require(_identifier(npc["id"]) and npc["id"] not in ids,
                "Invalid or duplicate living-world NPC identity")
        ids.add(npc["id"])
        schedule = npc["schedule"]
        require(type(schedule) is list and 1 <= len(schedule) <= MAX_STOPS,
                "NPC needs 1..32 daily schedule stops")
        previous = -1
        for stop in schedule:
            require(type(stop) is dict
                    and {"minute", "scene", "activity"} <= set(stop)
                    <= {"minute", "scene", "activity", "when"},
                    "Malformed NPC schedule stop")
            minute = stop["minute"]
            require(type(minute) is int and previous < minute < 1440,
                    "NPC schedule minutes must be unique, ordered and in 0..1439")
            previous = minute
            require(type(stop["scene"]) is str and stop["scene"] in scene_ids,
                    "NPC schedule references unknown scene")
            require(_identifier(stop["activity"]),
                    "Invalid NPC schedule activity")
            if "when" in stop:
                condition = stop["when"]
                require(type(condition) is dict
                        and set(condition) == {"flag", "eq"}
                        and _identifier(condition["flag"])
                        and type(condition["eq"]) is bool,
                        "NPC schedule condition must test a boolean story flag")


class LivingWorld:
    """Integer-time projection for all scenes, including scenes outside focus."""

    def __init__(self, spec, scene_ids):
        validate_living_world(spec, scene_ids)
        self.spec = deepcopy(spec)
        self.scene_ids = frozenset(scene_ids)
        self.ticks = 0

    @property
    def day(self):
        minutes = self.spec["start_minute"] + (
            self.ticks // self.spec["ticks_per_minute"])
        return minutes // 1440

    @property
    def minute(self):
        return (self.spec["start_minute"]
                + self.ticks // self.spec["ticks_per_minute"]) % 1440

    def preflight(self, ticks):
        require(type(ticks) is int and 1 <= ticks <= MAX_ADVANCE
                and self.ticks + ticks <= MAX_TICKS,
                "Invalid or overflowing living-world time advance")

    def advance(self, ticks=1):
        """Jump over arbitrarily many schedule boundaries in O(1) clock time."""
        self.preflight(ticks)
        self.ticks += ticks
        return self.snapshot()

    def snapshot(self):
        return {"version": VERSION, "ticks": self.ticks}

    def restore(self, data):
        require(type(data) is dict and set(data) == {"version", "ticks"}
                and type(data["version"]) is int and data["version"] == VERSION
                and type(data["ticks"]) is int
                and 0 <= data["ticks"] <= MAX_TICKS,
                "Invalid living-world checkpoint")
        self.ticks = data["ticks"]

    def view(self, story_flags, *, scene=None):
        """Return detached, ordered NPC projections; no state mutated."""
        require(type(story_flags) is dict, "Story flags must be a mapping")
        require(scene is None or scene in self.scene_ids,
                "Unknown living-world scene")
        rows = []
        current = self.minute
        for npc in self.spec["npcs"]:
            eligible = [stop for stop in npc["schedule"]
                        if "when" not in stop or
                        (story_flags.get(stop["when"]["flag"], False)
                         is stop["when"]["eq"])]
            if eligible:
                # Schedules recur daily. Before the first stop of a new day,
                # the last eligible stop from yesterday is still active.
                candidate = next((stop for stop in reversed(eligible)
                                  if stop["minute"] <= current), eligible[-1])
                location, activity = candidate["scene"], candidate["activity"]
            else:
                location, activity = None, "unavailable"
            if scene is None or location == scene:
                rows.append({"id": npc["id"], "scene": location,
                             "activity": activity})
        return {"version": VERSION, "day": self.day,
                "minute": current, "ticks": self.ticks, "npcs": rows}


__all__ = ["EXTENSION", "LivingWorld", "validate_living_world"]
