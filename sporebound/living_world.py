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
    required = {"version", "start_minute", "ticks_per_minute",
                "clock_policy", "npcs"}
    require(type(spec) is dict and required <= set(spec)
            <= required | {"factions", "daily_quests"},
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


    factions = spec.get("factions", [])
    require(type(factions) is list and len(factions) <= 64,
            "Invalid living-world factions")
    faction_ids = set()
    for faction in factions:
        require(type(faction) is dict
                and set(faction) == {"id", "initial"}
                and _identifier(faction["id"])
                and faction["id"] not in faction_ids
                and type(faction["initial"]) is int
                and -100 <= faction["initial"] <= 100,
                "Invalid or duplicate faction")
        faction_ids.add(faction["id"])
    quests = spec.get("daily_quests", [])
    require(type(quests) is list and len(quests) <= 128,
            "Invalid living-world daily quests")
    quest_ids = set()
    for quest in quests:
        require(type(quest) is dict and set(quest) ==
                {"id", "faction", "min_reputation", "start_minute",
                 "end_minute", "completion_flag", "reward_gold",
                 "reputation_delta"},
                "Malformed daily quest")
        require(_identifier(quest["id"]) and quest["id"] not in quest_ids
                and quest["faction"] in faction_ids
                and _identifier(quest["completion_flag"]),
                "Unknown faction, repeated quest, or invalid daily flag")
        quest_ids.add(quest["id"])
        require(type(quest["min_reputation"]) is int
                and -100 <= quest["min_reputation"] <= 100
                and type(quest["start_minute"]) is int
                and type(quest["end_minute"]) is int
                and 0 <= quest["start_minute"] < quest["end_minute"] <= 1440
                and type(quest["reward_gold"]) is int
                and 0 <= quest["reward_gold"] <= 10_000
                and type(quest["reputation_delta"]) is int
                and -100 <= quest["reputation_delta"] <= 100,
                "Daily quest has invalid hours or rewards")


class LivingWorld:
    """Integer-time projection for all scenes, including scenes outside focus."""

    def __init__(self, spec, scene_ids):
        validate_living_world(spec, scene_ids)
        self.spec = deepcopy(spec)
        self.scene_ids = frozenset(scene_ids)
        self.ticks = 0
        self.reputation = {f["id"]: f["initial"]
                           for f in self.spec.get("factions", [])}
        self.events = {}
        self.claimed = {}

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
        data = {"version": VERSION, "ticks": self.ticks}
        if "factions" in self.spec:
            data["reputation"] = deepcopy(self.reputation)
            data["events"] = deepcopy(self.events)
        if "daily_quests" in self.spec:
            data["claimed"] = deepcopy(self.claimed)
        return data

    def restore(self, data):
        expected = {"version", "ticks"}
        if "factions" in self.spec:
            expected |= {"reputation", "events"}
        if "daily_quests" in self.spec:
            expected.add("claimed")
        require(type(data) is dict and set(data) == expected
                and type(data["version"]) is int and data["version"] == VERSION
                and type(data["ticks"]) is int
                and 0 <= data["ticks"] <= MAX_TICKS,
                "Invalid living-world checkpoint")
        reputation = data.get("reputation", {})
        events = data.get("events", {})
        claimed = data.get("claimed", {})
        require(type(reputation) is dict and
                set(reputation) == set(self.reputation)
                and all(type(value) is int and -100 <= value <= 100
                        for value in reputation.values()),
                "Invalid living-world reputation checkpoint")
        require(type(events) is dict and len(events) <= 2048,
                "Invalid living-world reputation event ledger")
        for event_id, event in events.items():
            require(_identifier(event_id) and type(event) is dict
                    and set(event) == {"faction", "delta"}
                    and event["faction"] in self.reputation
                    and type(event["delta"]) is int
                    and -100 <= event["delta"] <= 100,
                    "Invalid reputation ledger event")
        require(type(claimed) is dict
                and set(claimed) <= {q["id"] for q in
                                    self.spec.get("daily_quests", [])}
                and all(type(day) is int
                        and 0 <= day <= (
                            self.spec["start_minute"] +
                            data["ticks"] // self.spec["ticks_per_minute"]) // 1440
                        for day in claimed.values()),
                "Invalid daily-quest checkpoint")
        self.ticks = data["ticks"]
        self.reputation = deepcopy(reputation)
        self.events = deepcopy(events)
        self.claimed = deepcopy(claimed)

    def adjust_reputation(self, faction, delta, event_id):
        """Commit one idempotent narrative event without a second quest registry."""
        require(type(faction) is str and faction in self.reputation
                and type(delta) is int and -100 <= delta <= 100
                and _identifier(event_id),
                "Invalid living-world reputation event")
        receipt = {"faction": faction, "delta": delta}
        if event_id in self.events:
            require(self.events[event_id] == receipt,
                    "Conflicting reputation event reuse")
            return False
        require(len(self.events) < 2048,
                "Reputation event ledger is full; explicit migration required")
        value = self.reputation[faction] + delta
        require(-100 <= value <= 100,
                "Living-world reputation exceeds -100..100")
        self.events[event_id] = receipt
        self.reputation[faction] = value
        return True

    def _quest(self, quest_id):
        require(_identifier(quest_id), "Invalid daily quest ID")
        quest = next((q for q in self.spec.get("daily_quests", [])
                      if q["id"] == quest_id), None)
        require(quest is not None, "Unknown daily quest")
        return quest

    def quest_ready(self, quest_id, story_flags):
        quest = self._quest(quest_id)
        return (self.claimed.get(quest_id) != self.day
                and quest["start_minute"] <= self.minute < quest["end_minute"]
                and self.reputation[quest["faction"]] >= quest["min_reputation"]
                and type(story_flags.get(quest["completion_flag"])) is int
                and story_flags[quest["completion_flag"]] == self.day)

    def finish_daily_quest(self, quest_id, progress):
        """Validate all conditions, then mutate existing Campaign rewards once."""
        quest = self._quest(quest_id)
        if self.claimed.get(quest_id) == self.day:
            return False
        require(self.quest_ready(quest_id, progress.story_flags),
                "Daily quest is not completed for the current day")
        reputation = self.reputation[quest["faction"]]
        delta = quest["reputation_delta"]
        require(-100 <= reputation + delta <= 100,
                "Daily quest reputation reward is out of bounds")
        require(type(progress.gold) is int and progress.gold >= 0
                and progress.gold + quest["reward_gold"] <= 2 ** 53 - 1,
                "Daily quest gold is outside portable range")
        # All potential failures are checked before any state is committed.
        progress.gold += quest["reward_gold"]
        self.reputation[quest["faction"]] = reputation + delta
        self.claimed[quest_id] = self.day
        return True

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
        data = {"version": VERSION, "day": self.day,
                "minute": current, "ticks": self.ticks, "npcs": rows}
        if "factions" in self.spec:
            data["reputation"] = deepcopy(self.reputation)
        if "daily_quests" in self.spec:
            data["daily_quests"] = [
                {"id": q["id"],
                 "claimed_today": self.claimed.get(q["id"]) == self.day,
                 "ready": self.quest_ready(q["id"], story_flags)}
                for q in self.spec["daily_quests"]]
        return data


__all__ = ["EXTENSION", "LivingWorld", "validate_living_world"]
