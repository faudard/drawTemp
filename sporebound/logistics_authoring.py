"""Pure, transactional editing of the existing LogisticsDirector configuration.

A siege without "logistics" retains its exact historical serialization.
Every edit returns a *new* blueprint after validating the actual multi-front
engine; rejected mutations cannot change the calling project or config.
"""
from copy import deepcopy

from .model import require
from .siege_authoring import set_logistics


def configuration(blueprint):
    saved = blueprint.get("logistics")
    if saved is not None:
        return deepcopy(saved)
    return {"routes": [], "reserves": {"player": 0, "enemy": 0},
            "capacity": 6, "supplies": {"player": 0, "enemy": 0},
            "escorts": 0, "ambushes": []}


def replace(blueprint, content, config):
    return set_logistics(blueprint, config, content)


def disable(blueprint, content):
    return set_logistics(blueprint, None, content)


def resources(blueprint, content, *, player_reserves, enemy_reserves,
              capacity, player_supplies, enemy_supplies, escorts):
    config = configuration(blueprint)
    config["reserves"] = {"player": player_reserves, "enemy": enemy_reserves}
    config["capacity"] = capacity
    config["supplies"] = {"player": player_supplies, "enemy": enemy_supplies}
    config["escorts"] = escorts
    return replace(blueprint, content, config)


def upsert_route(blueprint, content, origin, target, turns):
    config = configuration(blueprint)
    routes = config.setdefault("routes", [])
    row = {"from": origin, "to": target, "turns": turns}
    for index, current in enumerate(routes):
        if (current["from"], current["to"]) == (origin, target):
            routes[index] = row
            break
    else:
        routes.append(row)
    return replace(blueprint, content, config)


def delete_route(blueprint, content, origin, target):
    config = configuration(blueprint)
    require(any(route["from"] == origin and route["to"] == target
                for route in config.get("routes", [])), "Unknown logistics route")
    require(not any(row["from"] == origin and row["to"] == target
                    for row in config.get("ambushes", [])),
            "Remove the route ambush before removing its road")
    config["routes"] = [row for row in config["routes"]
                        if (row["from"], row["to"]) != (origin, target)]
    return replace(blueprint, content, config)


def upsert_ambush(blueprint, content, origin, target, *, casualties, delay, charges):
    config = configuration(blueprint)
    require(any(row["from"] == origin and row["to"] == target
                for row in config.get("routes", [])),
            "Ambush needs an existing logistics route")
    hazards = config.setdefault("ambushes", [])
    row = {"from": origin, "to": target, "casualties": casualties,
           "delay": delay, "charges": charges}
    for index, current in enumerate(hazards):
        if (current["from"], current["to"]) == (origin, target):
            hazards[index] = row
            break
    else:
        hazards.append(row)
    return replace(blueprint, content, config)


def delete_ambush(blueprint, content, origin, target):
    config = configuration(blueprint)
    require(any(row["from"] == origin and row["to"] == target
                for row in config.get("ambushes", [])), "Unknown route ambush")
    config["ambushes"] = [row for row in config["ambushes"]
                          if (row["from"], row["to"]) != (origin, target)]
    return replace(blueprint, content, config)


def rescue_mission(blueprint, content, mission_id):
    config = configuration(blueprint)
    if mission_id:
        config["rescue_mission"] = mission_id
    else:
        require("choices" not in config,
                "Disable advanced convoy choices before removing rescue mission")
        config.pop("rescue_mission", None)
    return replace(blueprint, content, config)


def preview(blueprint, content):
    """Return the engine's initial logistics state, not fake convoy outcomes."""
    from .siege_authoring import make_session
    session = make_session(blueprint, content)
    require(session.logistics is not None, "Logistics not configured")
    return session.logistics.state()
