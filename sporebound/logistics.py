"""Bounded strategic logistics for small tactical fronts.

No autonomous tactical simulation runs in transit. A convoy is a deterministic
order that reaches its destination only on a subsequent strategic turn.
"""
from copy import deepcopy
from dataclasses import asdict

from .actors import ActorFactory, validate_actor
from .model import require


class LogisticsDirector:
    def __init__(self, config, missions):
        require(isinstance(config, dict) and set(config) <= {"routes", "reserves", "capacity"},
                "Invalid logistics configuration")
        require("reserve" not in missions, "reserve is a reserved strategic origin")
        reserves = config.get("reserves", {})
        require(isinstance(reserves, dict) and set(reserves) <= {"player", "enemy"},
                "Invalid logistics reserves")
        require(all(type(n) is int and 0 <= n <= 10000 for n in reserves.values()),
                "Invalid logistics reserve amount")
        capacity = config.get("capacity", 6)
        require(type(capacity) is int and 1 <= capacity <= 100,
                "Invalid logistics convoy capacity")
        self.capacity = capacity
        self.reserves = {"player": reserves.get("player", 0),
                         "enemy": reserves.get("enemy", 0)}
        raw_routes = config.get("routes", [])
        require(isinstance(raw_routes, list), "Invalid logistics routes")
        self.routes = {}
        for route in raw_routes:
            require(isinstance(route, dict) and set(route) == {"from", "to", "turns"},
                    "Invalid logistics route")
            origin, dest, turns = route["from"], route["to"], route["turns"]
            require(isinstance(origin, str) and isinstance(dest, str)
                    and origin in {*missions, "reserve"} and dest in missions
                    and origin != dest, "Unknown logistics route")
            require(type(turns) is int and 1 <= turns <= 100,
                    "Travel time must be 1..100 strategic turns")
            require((origin, dest) not in self.routes, "Duplicate logistics route")
            self.routes[(origin, dest)] = turns
        self.in_transit = []
        self.serial = 0

    def travel_time(self, origin, destination):
        require((origin, destination) in self.routes,
                "No logistics route between these fronts")
        return self.routes[(origin, destination)]

    def capacity_available(self, count):
        require(type(count) is int and count > 0
                and sum(len(order["actors"]) for order in self.in_transit)
                + count <= self.capacity, "Convoy capacity exceeded")

    def order(self, origin, destination, actors, team, turn):
        turns = self.travel_time(origin, destination)
        require(isinstance(actors, list) and actors and
                all(isinstance(actor, dict) for actor in actors),
                "Convoy needs concrete actors")
        self.capacity_available(len(actors))
        require(len(actors) <= 14, "A convoy may contain at most 14 tactical actors")
        require(team in {"player", "enemy"}
                and all(actor.get("team") == team for actor in actors),
                "Convoy cannot mix teams")
        self.serial += 1
        order = {"id": f"convoy_{self.serial}", "from": origin, "to": destination,
                 "team": team, "arrival": turn + turns, "actors": deepcopy(actors)}
        self.in_transit.append(order)
        return order["id"]

    def due(self, turn):
        ready = [row for row in self.in_transit if row["arrival"] <= turn]
        self.in_transit = [row for row in self.in_transit if row["arrival"] > turn]
        return ready

    def state(self):
        return {"capacity": self.capacity, "reserves": deepcopy(self.reserves),
                "routes": [{"from": src, "to": dst, "turns": ticks}
                           for (src, dst), ticks in sorted(self.routes.items())],
                "in_transit": deepcopy(self.in_transit), "serial": self.serial}


def destination_actors(session, front, definitions):
    """Validate actor identity, destination footprint and JSON-facing payloads.

    Destination cells may currently be occupied by a combatant. The encounter
    queue will keep that wave pending until the landing zone is available.
    """
    from .deployment import cell
    require(isinstance(definitions, list) and bool(definitions),
            "Convoy needs a nonempty actor list")
    mission = session.content.missions[session.missions[front]]
    occupied_ids = {u.id for u in mission.units}
    if front in session.battles:
        occupied_ids.update(u.id for u in session.battles[front].units)
        for wave in session.battles[front].encounter.pending:
            occupied_ids.update(actor["id"] for actor in wave["actors"])
    for wave in session.pending_reinforcements.get(front, []):
        occupied_ids.update(actor["id"] for actor in wave["actors"])
    if session.logistics:
        for order in session.logistics.in_transit:
            if order["to"] == front:
                occupied_ids.update(actor["id"] for actor in order["actors"])
    actors = []
    footprints = set()
    factory = ActorFactory(session.content.archetypes)
    for definition in definitions:
        require(isinstance(definition, dict) and isinstance(definition.get("id"), str)
                and bool(definition["id"]) and definition["id"] not in occupied_ids,
                "Duplicate or invalid convoy actor")
        actor = factory.create(definition)
        validate_actor(actor, session.content.skills, session.content.archetypes,
                       session.rules)
        require(actor.kind != "summon", "Summons cannot be transported by convoy")
        occupied_ids.add(actor.id)
        anchor = cell(actor.pos)
        footprint = actor.occupied_cells(anchor)
        require(not footprints.intersection(footprint), "Overlapping convoy landing cells")
        require(all(mission.board.contains(pos)
                    and not mission.board.tile(pos).blocked
                    and not any(obj["kind"] == "door"
                                and tuple(obj["pos"]) == pos and not
                                session.front_overrides.get(front, {}).get(
                                    obj["id"], {}).get("open", obj.get("open", False))
                                for obj in mission.objects)
                    for pos in footprint),
                "Invalid convoy landing footprint")
        footprints.update(footprint)
        actors.append(asdict(actor))
    return actors
