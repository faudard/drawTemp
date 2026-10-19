"""R33.A — bounded, read-only ability-gated room reachability.

The graph lives in the canonical GameProject.extensions namespace
``drawtemp.metroidvania``. Room IDs reference existing exploration scenes;
this is not a side-view renderer, physics engine, or second world registry.
"""
from __future__ import annotations

from collections import defaultdict, deque
import re

from .model import RuleError

NAMESPACE = "drawtemp.metroidvania"
MAX_ROOMS = 128
MAX_LINKS = 512
MAX_PICKUPS = 32
MAX_CAPABILITIES = 12
MAX_STATES = 50000
_IDENT = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


def _fail(message):
    raise RuleError("R33 metroidvania: " + message)


def _id(value):
    return type(value) is str and _IDENT.fullmatch(value) is not None


def _ids(value, limit, kind):
    if (type(value) is not list or len(value) > limit
            or any(not _id(item) for item in value)
            or len(set(value)) != len(value)):
        _fail("invalid or duplicated " + kind)
    return value


def validate_metroidvania(raw, *, scene_ids=None):
    """Validate v1 preflight data, with fail-closed refs and bounded cardinality.

    A scene reference is an authored GameProject.exploration scene, never a
    parallel level definition. This module does not register an active genre.
    """
    if type(raw) is not dict or set(raw) != {
            "version", "rooms", "start", "goal", "links", "pickups",
            "starting_capabilities"}:
        _fail("expected exact v1 world graph fields")
    if type(raw["version"]) is not int or raw["version"] != 1:
        _fail("unsupported graph version; explicit migration required")
    rooms = _ids(raw["rooms"], MAX_ROOMS, "rooms")
    if not rooms or raw["start"] not in rooms or raw["goal"] not in rooms:
        _fail("start and goal must reference authored rooms")
    if scene_ids is not None and not set(rooms) <= set(scene_ids):
        _fail("room references an unknown exploration scene")
    starting = _ids(raw["starting_capabilities"], MAX_CAPABILITIES,
                    "starting capabilities")
    if type(raw["pickups"]) is not list or len(raw["pickups"]) > MAX_PICKUPS:
        _fail("invalid pickup list")
    pickups, discovered = set(), set(starting)
    for pickup in raw["pickups"]:
        if (type(pickup) is not dict
                or set(pickup) != {"id", "room", "grants"}
                or not _id(pickup["id"]) or pickup["id"] in pickups
                or pickup["room"] not in rooms):
            _fail("invalid pickup ID or room")
        pickups.add(pickup["id"])
        grants = _ids(pickup["grants"], MAX_CAPABILITIES, "pickup grants")
        if not grants:
            _fail("pickup must grant at least one capability")
        discovered.update(grants)
    if len(discovered) > MAX_CAPABILITIES:
        _fail("too many distinct capabilities")
    if type(raw["links"]) is not list or len(raw["links"]) > MAX_LINKS:
        _fail("invalid link list")
    link_ids = set()
    for link in raw["links"]:
        if (type(link) is not dict
                or set(link) != {"id", "source", "destination", "requires"}
                or not _id(link["id"]) or link["id"] in link_ids
                or link["source"] not in rooms
                or link["destination"] not in rooms
                or link["source"] == link["destination"]):
            _fail("invalid or dangling room link")
        link_ids.add(link["id"])
        if not set(_ids(link["requires"], MAX_CAPABILITIES,
                        "link requirements")) <= discovered:
            _fail("link requires an undefined capability")
    return True


def analyze_metroidvania(raw, *, scene_ids=None, state_budget=20000):
    """Exhaustive *abstract* progression check up to a strict state budget.

    Items are monotonic ability grants on entering rooms. Doors use AND-gates.
    Each directed link is traversed separately, so one-way softlocks matter.
    Does not assert jump distances, physical collisions, combat or boss wins.
    """
    validate_metroidvania(raw, scene_ids=scene_ids)
    if type(state_budget) is not int or not 1 <= state_budget <= MAX_STATES:
        _fail("state budget must be 1..50000")
    abilities = sorted(set(raw["starting_capabilities"]) |
                       {cap for pickup in raw["pickups"]
                        for cap in pickup["grants"]})
    cap_bits = {name: 1 << i for i, name in enumerate(abilities)}
    grants = defaultdict(int)
    for pickup in raw["pickups"]:
        for cap in pickup["grants"]:
            grants[pickup["room"]] |= cap_bits[cap]
    links = defaultdict(list)
    for link in raw["links"]:
        required = 0
        for cap in link["requires"]:
            required |= cap_bits[cap]
        links[link["source"]].append((link["id"], link["destination"], required))
    for rows in links.values():
        rows.sort()  # deterministic witness and error ordering
    initial_bits = 0
    for cap in raw["starting_capabilities"]:
        initial_bits |= cap_bits[cap]
    initial = (raw["start"], initial_bits | grants[raw["start"]])
    queue = deque([initial])
    parents = {initial: None}
    reverse = defaultdict(set)
    terminals = set()
    budget_hit = False
    while queue:
        state = queue.popleft()
        room, bits = state
        if room == raw["goal"]:
            terminals.add(state)
            continue  # completing the game is a terminal state
        for link_id, dest, required in links[room]:
            if bits & required != required:
                continue
            successor = (dest, bits | grants[dest])
            if successor not in parents:
                if len(parents) >= state_budget:
                    budget_hit = True
                    break
                parents[successor] = (state, link_id)
                queue.append(successor)
            reverse[successor].add(state)
        if budget_hit:
            break
    if budget_hit:
        return {
            "complete": False, "safe": False, "goal_reachable": bool(terminals),
            "unreachable_rooms": [], "softlock_states": [], "witness": [],
            "visited_states": len(parents),
            "warnings": ["State budget exceeded; result is inconclusive"],
        }
    good = set(terminals)
    pending = deque(sorted(terminals))
    while pending:
        for prior in sorted(reverse[pending.popleft()]):
            if prior not in good:
                good.add(prior)
                pending.append(prior)
    dead = sorted(set(parents) - good)
    rooms_seen = {room for room, _ in parents}
    witness = []
    if terminals:
        end = min(terminals, key=lambda s: (s[1].bit_count(), s[0], s[1]))
        while end is not None:
            parent = parents[end]
            witness.append({
                "room": end[0],
                "capabilities": [a for a in abilities if end[1] & cap_bits[a]],
                "via": parent[1] if parent is not None else None,
            })
            end = parent[0] if parent is not None else None
        witness.reverse()
    return {
        "complete": True,
        "safe": bool(terminals) and not dead,
        "goal_reachable": bool(terminals),
        "unreachable_rooms": sorted(set(raw["rooms"]) - rooms_seen),
        "softlock_states": [{"room": room,
                             "capabilities": [a for a in abilities if bits & cap_bits[a]]}
                            for room, bits in dead[:100]],
        "witness": witness,
        "visited_states": len(parents),
        "warnings": (["Softlock states truncated to first 100"]
                     if len(dead) > 100 else []),
    }


__all__ = ["NAMESPACE", "validate_metroidvania", "analyze_metroidvania"]
