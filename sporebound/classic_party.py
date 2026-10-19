"""R41.A — opt-in classic RPG party contract; GameSession owns runtime state.

The authored roster belongs to GameProject.extensions; the mutable member/
active selection belongs exclusively to GameSession. HeroProgress, equipment,
gold and inventory remain in the canonical Campaign. Nothing changes CT.
"""
from __future__ import annotations

from copy import deepcopy

from .game_modes import resolve_scene_profile
from .model import require

EXTENSION = "drawtemp.party_rpg"
VERSION = 1
MAX_PARTY_EVENTS = 512


def _ids(value, *, max_count=64, allow_empty=False):
    require(type(value) is list and len(value) <= max_count
            and (allow_empty or len(value) > 0),
            "Invalid classic party member list")
    require(all(type(uid) is str and 0 < len(uid) <= 64
                and all(c.isalnum() or c in "-_" for c in uid)
                for uid in value), "Invalid classic party hero ID")
    require(len(value) == len(set(value)), "Duplicate classic party hero")
    return list(value)


def validate_classic_party(data, *, content, project):
    """Validate the whole versioned extension, including canonical references.

    Unknown keys, bool integers, non-player IDs and unsupported future schemas
    are errors, not migrations. Legacy projects do not need this extension.
    """
    require(type(data) is dict and set(data) == {"version", "campaigns"}
            and type(data["version"]) is int and data["version"] == VERSION,
            "Unsupported R41 party schema")
    campaigns = data["campaigns"]
    require(type(campaigns) is dict and 0 < len(campaigns) <= 32,
            "Classic party needs bounded campaign definitions")
    known_campaigns = {c["id"] for c in project.campaigns}
    players = {unit.id for mission in content.missions.values()
               for unit in mission.units if unit.team == "player"}
    has_rpg_profile = (resolve_scene_profile(project.game_modes)["combat"]
                       == "RPG_TURN" or any(
        resolve_scene_profile(project.game_modes, sid)["combat"] == "RPG_TURN"
        for sid in (set(project.exploration) |
                    {s["id"] for s in project.story.get("scenes", [])})))
    require(has_rpg_profile,
            "R41 party requires an explicit RPG_TURN project or scene profile")
    for cid, entry in campaigns.items():
        require(type(cid) is str and cid in known_campaigns,
                "Unknown classic party campaign")
        require(type(entry) is dict and set(entry) ==
                {"recruitable", "initial", "active", "max_active"},
                "Invalid classic party configuration")
        recruitable = _ids(entry["recruitable"])
        initial = _ids(entry["initial"])
        active = _ids(entry["active"], max_count=8)
        capacity = entry["max_active"]
        require(type(capacity) is int and 1 <= capacity <= 8,
                "Party capacity must be 1..8")
        require(len(active) <= capacity
                and set(active) <= set(initial) <= set(recruitable)
                and set(recruitable) <= players,
                "Invalid active/initial/recruitable hero references")
    return deepcopy(data)


class ClassicParty:
    """Session-owned roster selection with a replay-verified, bounded journal."""

    def __init__(self, config):
        self._config = deepcopy(config)
        self._allowed = frozenset(config["recruitable"])
        self._initial = tuple(config["initial"])
        self.capacity = config["max_active"]
        self.members = list(self._initial)
        self.active = list(config["active"])
        self.events = []

    def snapshot(self):
        return {"version": VERSION, "members": list(self.members),
                "active": list(self.active), "events": deepcopy(self.events)}

    def recruit(self, uid):
        require(type(uid) is str and uid in self._allowed
                and uid not in self.members, "Hero is unavailable or already recruited")
        require(len(self.events) < MAX_PARTY_EVENTS, "R41 party journal is full")
        self.members.append(uid)
        self.events.append({"op": "recruit", "hero": uid})
        return self.snapshot()

    def set_active(self, members):
        ordered = _ids(members, max_count=8)
        require(0 < len(ordered) <= self.capacity
                and set(ordered) <= set(self.members),
                "Active group must contain recruited heroes within capacity")
        require(ordered != self.active, "Active party is already selected")
        require(len(self.events) < MAX_PARTY_EVENTS, "R41 party journal is full")
        self.active = ordered
        self.events.append({"op": "activate", "members": list(ordered)})
        return self.snapshot()

    def restore(self, recording):
        """Replay from authored initial state, then compare the declared state."""
        require(type(recording) is dict and set(recording) ==
                {"version", "members", "active", "events"}
                and type(recording["version"]) is int
                and recording["version"] == VERSION
                and type(recording["events"]) is list
                and len(recording["events"]) <= MAX_PARTY_EVENTS,
                "Malformed classic party checkpoint")
        recreated = type(self)(self._config)
        for event in recording["events"]:
            require(type(event) is dict and "op" in event,
                    "Malformed classic party journal event")
            if event["op"] == "recruit":
                require(set(event) == {"op", "hero"},
                        "Invalid recruitment event")
                recreated.recruit(event["hero"])
            elif event["op"] == "activate":
                require(set(event) == {"op", "members"},
                        "Invalid active-party event")
                recreated.set_active(event["members"])
            else:
                require(False, "Unknown classic party journal action")
        require(recreated.snapshot() == recording,
                "Classic party checkpoint diverges from its replay")
        self.members, self.active, self.events = (
            recreated.members, recreated.active, recreated.events)


def rpg_turn_order(participants):
    """Pure RPG_TURN initiative primitive; does not modify tactical CT.

    Each participant is {"id": str, "speed": int, "team": "party"|"enemy"}.
    This is *not* an encounter executor or an alternate combat engine.
    """
    require(type(participants) is list and 1 <= len(participants) <= 32,
            "Invalid RPG_TURN participant count")
    seen = set()
    for entry in participants:
        require(type(entry) is dict and set(entry) ==
                {"id", "speed", "team"}, "Malformed RPG_TURN participant")
        uid = entry["id"]
        require(type(uid) is str and 0 < len(uid) <= 64
                and all(c.isalnum() or c in "-_" for c in uid)
                and uid not in seen, "Duplicate/invalid RPG_TURN actor")
        seen.add(uid)
        require(type(entry["speed"]) is int and 1 <= entry["speed"] <= 999
                and entry["team"] in ("party", "enemy"),
                "Invalid RPG_TURN speed/team")
    return tuple(row["id"] for row in sorted(
        participants, key=lambda row: (-row["speed"], row["id"])))


__all__ = ["EXTENSION", "VERSION", "ClassicParty",
           "validate_classic_party", "rpg_turn_order"]
