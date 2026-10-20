"""R53.A: replay-verified orchestration over R41's canonical active roster.

No new party, inventory, hero progression, action engine or CT authority.
"""
from copy import deepcopy
from .model import require

VERSION = 1
MAX_EVENTS = 512
SLOTS = ("front", "left", "right", "rear", "support", "flank_left",
         "flank_right", "second_rear")
MODES = ("TACTICAL_CT", "RPG_TURN", "ACTION_REALTIME")
PAUSE_POLICY = "freeze_on_encounter"


def _id(value):
    return (type(value) is str and 1 <= len(value) <= 64
            and all(c.isalnum() or c in "-_" for c in value))


def validate_orchestration(data, *, campaigns, content=None):
    require(type(data) is dict and {"version", "pause_policy", "combos"} <= set(data)
            and set(data) <= {"version", "pause_policy", "combos", "defaults"}
            and type(data["version"]) is int and data["version"] == VERSION
            and data["pause_policy"] == PAUSE_POLICY,
            "Unsupported R53 orchestration version or pause policy")
    combos = data["combos"]
    require(type(combos) is list and len(combos) <= 64, "Invalid R53 combos")
    ids = set()
    for row in combos:
        require(type(row) is dict and {"id", "members", "modes"} <= set(row)
                and set(row) <= {"id", "members", "modes", "skills"},
                "Invalid R53 cooperative ability fields")
        uid, members, modes = row["id"], row["members"], row["modes"]
        require(_id(uid) and uid not in ids, "Invalid/duplicate R53 combo ID")
        ids.add(uid)
        require(type(members) is list and 2 <= len(members) <= 4
                and all(_id(hero) for hero in members)
                and len(set(members)) == len(members)
                and any(set(members) <= set(c["recruitable"])
                        for c in campaigns.values()),
                "R53 combo requires distinct canonical recruitable actors")
        require(type(modes) is list and 1 <= len(modes) <= 3
                and all(type(m) is str and m in MODES for m in modes)
                and len(set(modes)) == len(modes),
                "Invalid R53 combat mode capabilities")
        if "skills" in row:
            skills = row["skills"]
            require("RPG_TURN" in modes
                    and type(skills) is dict
                    and set(skills) == set(members)
                    and all(_id(name) for name in skills.values()),
                    "R53 executable combo requires one canonical skill per hero")
            if content is not None:
                # Mirror R41's first-defined player-unit lookup precisely.
                players = {}
                for mission in content.missions.values():
                    for unit in mission.units:
                        if unit.team == "player":
                            players.setdefault(unit.id, unit)
                for hero in members:
                    skill_id = skills[hero]
                    require(hero in players
                            and skill_id in players[hero].skills
                            and skill_id in content.skills,
                            "R53 combo skill not owned by canonical playable actor")
                    skill = content.skills[skill_id]
                    require(skill.target == "enemy"
                            and bool(skill.effects)
                            and all(effect.kind == "damage"
                                    for effect in skill.effects),
                            "R53.A2 permits only native enemy damage skills")
    if "defaults" in data:
        defaults = data["defaults"]
        require(type(defaults) is dict and len(defaults) <= len(campaigns)
                and set(defaults) <= set(campaigns),
                "R53 defaults must reference configured party campaigns")
        for cid, row in defaults.items():
            active = campaigns[cid]["active"]
            require(type(row) is dict and set(row) == {"leader", "formation"}
                    and type(row["leader"]) is str and row["leader"] in active
                    and type(row["formation"]) is list
                    and len(row["formation"]) == len(active)
                    and all(type(slot) is str and slot in SLOTS
                            for slot in row["formation"])
                    and len(set(row["formation"])) == len(active),
                    "R53 default leader/formation require active heroes and unique slots")
    return deepcopy(data)


class PartyOrchestration:
    """Session-owned leader/slots; R41 still owns active member selection."""

    def __init__(self, specification, config, *, campaign_id=None):
        key = campaign_id if campaign_id is not None else "current"
        # The document was validated against *all* campaigns by GameProject.
        # This session owns just one campaign; ignore unrelated defaults here.
        local = deepcopy(specification)
        if "defaults" in local:
            local["defaults"] = {
                key: local["defaults"][key]} if key in local["defaults"] else {}
        validate_orchestration(local, campaigns={key: config})
        self._spec = deepcopy(specification)
        self._config = deepcopy(config)
        self._campaign_id = key
        self.active = list(config["active"])
        defaults = specification.get("defaults", {}).get(key, {})
        self.leader = defaults.get("leader", self.active[0])
        self.formation = list(defaults.get("formation", SLOTS[:len(self.active)]))
        self.events = []

    @property
    def pause_policy(self):
        return PAUSE_POLICY

    def snapshot(self):
        return {"version": VERSION, "active": list(self.active),
                "leader": self.leader, "formation": list(self.formation),
                "events": deepcopy(self.events)}

    def _room(self):
        require(len(self.events) < MAX_EVENTS, "R53 journal is full")

    def activate(self, heroes):
        """Mirror a successful R41 activation; never recruit independently."""
        require(type(heroes) is list and 1 <= len(heroes) <= 8
                and all(_id(hero) for hero in heroes)
                and len(set(heroes)) == len(heroes)
                and set(heroes) <= set(self._config["recruitable"])
                and heroes != self.active, "Invalid R53 R41 synchronization")
        self._room()
        self.active = list(heroes)
        self.leader = self.leader if self.leader in heroes else heroes[0]
        self.formation = list(SLOTS[:len(heroes)])
        self.events.append({"op": "active", "heroes": list(heroes)})
        return self.snapshot()

    def switch_leader(self, hero):
        require(_id(hero) and hero in self.active and hero != self.leader,
                "R53 leader must be a different active member")
        self._room()
        self.leader = hero
        self.events.append({"op": "leader", "hero": hero})
        return self.snapshot()

    def set_formation(self, slots):
        require(type(slots) is list and len(slots) == len(self.active)
                and all(type(slot) is str and slot in SLOTS for slot in slots)
                and len(set(slots)) == len(slots) and slots != self.formation,
                "R53 formation needs distinct supported slots")
        self._room()
        self.formation = list(slots)
        self.events.append({"op": "formation", "slots": list(slots)})
        return self.snapshot()

    def eligible_combos(self, combat):
        """Read-only eligibility; R43 combat effects are not executed by R53.A."""
        require(type(combat) is str and combat in MODES,
                "Unsupported R53 combat mode")
        active = set(self.active)
        return [c["id"] for c in self._spec["combos"]
                if combat in c["modes"] and set(c["members"]) <= active]

    def rpg_combo_specs(self):
        """Detached executable RPG_TURN combos; other modes are not yet runnable."""
        active = set(self.active)
        return deepcopy([row for row in self._spec["combos"]
                         if "skills" in row and "RPG_TURN" in row["modes"]
                         and set(row["members"]) <= active])

    def restore(self, recording, party):
        """Replay journal and cross-check every activation with R41 history."""
        require(type(recording) is dict
                and set(recording) == {"version", "active", "leader",
                                       "formation", "events"}
                and type(recording["version"]) is int
                and recording["version"] == VERSION
                and type(recording["events"]) is list
                and len(recording["events"]) <= MAX_EVENTS,
                "Invalid R53 orchestration checkpoint")
        activations = [row["members"] for row in party.events
                       if row["op"] == "activate"]
        candidate = type(self)(self._spec, self._config,
                               campaign_id=self._campaign_id)
        consumed = 0
        for event in recording["events"]:
            require(type(event) is dict and type(event.get("op")) is str,
                    "Malformed R53 journal event")
            if event["op"] == "active":
                require(set(event) == {"op", "heroes"}
                        and consumed < len(activations)
                        and event["heroes"] == activations[consumed],
                        "R53 activation missing from R41 journal")
                candidate.activate(event["heroes"])
                consumed += 1
            elif event["op"] == "leader":
                require(set(event) == {"op", "hero"}, "Invalid R53 leader event")
                candidate.switch_leader(event["hero"])
            elif event["op"] == "formation":
                require(set(event) == {"op", "slots"}, "Invalid R53 formation event")
                candidate.set_formation(event["slots"])
            else:
                require(False, "Unknown R53 journal action")
        require(consumed == len(activations) and candidate.active == party.active
                and candidate.snapshot() == recording,
                "R53 checkpoint diverges from its R41-backed replay")
        self.active, self.leader, self.formation, self.events = (
            candidate.active, candidate.leader, candidate.formation,
            candidate.events)


__all__ = ["PartyOrchestration", "validate_orchestration",
           "SLOTS", "MAX_EVENTS", "PAUSE_POLICY"]
