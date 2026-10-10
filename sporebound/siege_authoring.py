"""Validated visual authoring of deterministic multi-front siege plans.

A plan is stored optionally in GameProject.sieges[campaign_id]. The exact
runtime fields are handed to GameSession.start_fronts; older projects, slots,
recordings and command streams remain unchanged.
"""
from copy import deepcopy

from .fronts import DOCTRINES, FrontDirector
from .logistics import LogisticsDirector
from .model import require


def validate_plan(plan, content):
    """Validate and return an isolated canonical plan; never mutate inputs."""
    require(isinstance(plan, dict) and set(plan) == {
        "missions", "focused", "specs", "logistics"}, "Invalid siege plan")
    missions = plan["missions"]
    require(isinstance(missions, dict) and 2 <= len(missions) <= 20,
            "A siege needs 2..20 strategic fronts")
    for front, mission in missions.items():
        require(isinstance(front, str) and 0 < len(front) <= 64
                and all(ch.isalnum() or ch in "_-" for ch in front)
                and front != "reserve", "Invalid front identifier")
        require(isinstance(mission, str) and mission in content.missions,
                "Siege front references an unknown mission")
    require(len(set(missions.values())) == len(missions),
            "One mission cannot serve multiple simultaneous fronts")
    focused = plan["focused"]
    require(isinstance(focused, str) and focused in missions,
            "Siege needs a focused starting front")
    specs = plan["specs"]
    require(isinstance(specs, dict) and set(specs) == set(missions),
            "Front specifications must match authored fronts")
    require(all(isinstance(value, dict)
                and set(value) == {"strength", "opposition", "doctrine"}
                for value in specs.values()), "Invalid front specifications")
    FrontDirector(specs, focused)
    require(all(row["doctrine"] in DOCTRINES for row in specs.values()),
            "Unsupported siege doctrine")
    logistics = plan["logistics"]
    require(isinstance(logistics, dict)
            and set(logistics) == {"routes", "reserves", "capacity"},
            "Invalid siege logistics configuration")
    LogisticsDirector(logistics, missions)
    return deepcopy(plan)


def new_plan(content, first, second):
    require(first != second and first in content.missions
            and second in content.missions, "Choose two different missions")
    plan = {
        "missions": {first: first, second: second},
        "focused": first,
        "specs": {front: {"strength": 10, "opposition": 10, "doctrine": "hold"}
                  for front in (first, second)},
        "logistics": {"routes": [], "reserves": {"player": 3, "enemy": 0},
                      "capacity": 4},
    }
    return validate_plan(plan, content)


def put_front(plan, content, front, mission, strength, opposition, doctrine):
    """Add or update a front atomically, rejecting references and duplicates."""
    result = deepcopy(plan)
    result["missions"][front] = mission
    result["specs"][front] = {"strength": strength, "opposition": opposition,
                              "doctrine": doctrine}
    return validate_plan(result, content)


def delete_front(plan, content, front):
    result = deepcopy(plan)
    require(front in result["missions"], "Unknown front")
    require(len(result["missions"]) > 2, "A siege needs at least two fronts")
    del result["missions"][front]
    del result["specs"][front]
    result["logistics"]["routes"] = [
        row for row in result["logistics"]["routes"]
        if front not in (row["from"], row["to"])]
    if result["focused"] == front:
        result["focused"] = next(iter(sorted(result["missions"])))
    return validate_plan(result, content)


def set_focus(plan, content, front):
    result = deepcopy(plan)
    result["focused"] = front
    return validate_plan(result, content)


def put_route(plan, content, origin, destination, turns):
    """Create or update a directed route, including reserve -> front links."""
    result = deepcopy(plan)
    routes = result["logistics"]["routes"]
    row = next((item for item in routes
                if item["from"] == origin and item["to"] == destination), None)
    if row is not None:
        row["turns"] = turns
    else:
        routes.append({"from": origin, "to": destination, "turns": turns})
    return validate_plan(result, content)


def delete_route(plan, content, origin, destination):
    result = deepcopy(plan)
    routes = result["logistics"]["routes"]
    result["logistics"]["routes"] = [
        row for row in routes if (row["from"], row["to"]) != (origin, destination)]
    require(len(result["logistics"]["routes"]) < len(routes),
            "Unknown logistics route")
    return validate_plan(result, content)


def set_logistics(plan, content, player_reserves, enemy_reserves, capacity):
    result = deepcopy(plan)
    result["logistics"]["reserves"] = {
        "player": player_reserves, "enemy": enemy_reserves}
    result["logistics"]["capacity"] = capacity
    return validate_plan(result, content)


def strategy_preview(plan, content, turns=5):
    """Pure strategic forecast; never executes battles or consumes game saves."""
    plan = validate_plan(plan, content)
    require(type(turns) is int and 0 <= turns <= 30,
            "Preview needs 0..30 strategic turns")
    director = FrontDirector(plan["specs"], plan["focused"])
    result = [director.state()]
    for _ in range(turns):
        result.append(director.advance())
    return result
