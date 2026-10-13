"""3.7.24A — optional, authored campaign world map.

World nodes are *presentation coordinates* attached to existing Mission IDs.
Mission.next_missions remains the only travel/unlock graph; no new gameplay
routes, save-slot state, or tactical board coordinates are introduced.
"""
from copy import deepcopy
from math import ceil

from .model import require

WORLD_THEMES = ("parchment", "kingdom", "forest", "winter")
WORLD_WIDTH = 960
WORLD_HEIGHT = 640
MAX_WORLD_NODES = 160


def validate_world(raw, content, campaigns, story=None):
    """Validate world presentation and optional canonical narrative road events."""
    require(isinstance(raw, dict), "World must be an object")
    if not raw:
        return
    required = {"width", "height", "theme", "nodes"}
    require(required <= set(raw) <= required | {"events"},
            "World needs width, height, theme, nodes and optional events")
    width, height = raw["width"], raw["height"]
    require(type(width) is int and 480 <= width <= 4000
            and type(height) is int and 320 <= height <= 4000,
            "Invalid world canvas dimensions")
    require(raw["theme"] in WORLD_THEMES, "Unknown world theme")
    nodes = raw["nodes"]
    require(isinstance(nodes, list) and 1 <= len(nodes) <= MAX_WORLD_NODES,
            "World needs 1..160 mission locations")
    seen = set()
    for node in nodes:
        require(isinstance(node, dict) and set(node) ==
                {"mission", "x", "y", "region"}, "Invalid world location fields")
        mid = node["mission"]
        require(isinstance(mid, str) and mid in content.missions
                and mid not in seen, "Duplicate or unknown world mission")
        seen.add(mid)
        require(type(node["x"]) is int and 24 <= node["x"] <= width - 24
                and type(node["y"]) is int and 24 <= node["y"] <= height - 24,
                "World location lies outside map margins")
        region = node["region"]
        require(isinstance(region, str) and len(region) <= 64,
                "World region name too long")
    # Road events are authoring links to StoryBook scenes, not a new dialogue
    # engine. Both road endpoints must belong to the actual mission graph.
    events = raw.get("events", [])
    require(isinstance(events, list) and len(events) <= 80,
            "World needs at most 80 road events")
    event_ids, event_positions = set(), set()
    scene_catalog = ({scene["id"]: scene for scene in story.get("scenes", [])}
                     if story is not None else None)
    for event in events:
        require(isinstance(event, dict) and
                {"id", "from", "to", "scene"} <= set(event) <=
                {"id", "from", "to", "scene", "when", "step", "routes"},
                "Invalid world road event")
        eid, source, target = event["id"], event["from"], event["to"]
        require(isinstance(eid, str) and 0 < len(eid) <= 24 and
                all(ch.isascii() and (ch.isalnum() or ch == "_") for ch in eid)
                and eid not in event_ids, "Duplicate or invalid road event id")
        event_ids.add(eid)
        require(isinstance(source, str) and isinstance(target, str)
                and source != target and source in seen and target in seen
                and (target in content.missions[source].next_missions or
                     source in content.missions[target].next_missions),
                "World event must reference a real road between visible missions")
        step = event.get("step", 4)
        require(type(step) is int and 1 <= step < 8,
                "World event step must be within its road")
        position = (*sorted((source, target)),
                    step if source < target else 8 - step)
        require(position not in event_positions,
                "Two road events cannot occupy the same position")
        event_positions.add(position)
        scene_id = event["scene"]
        require(isinstance(scene_id, str) and
                (scene_catalog is None or scene_id in scene_catalog),
                "World road event references an unknown narrative scene")
        if "when" in event:
            from .narrative import _condition
            _condition(event["when"], content)
        routes = event.get("routes", {})
        require(isinstance(routes, dict) and len(routes) <= 20,
                "Invalid world-event choice routes")
        scene_choices = ({choice["id"] for choice in
                          scene_catalog[scene_id]["choices"]}
                         if scene_catalog is not None else None)
        for choice_id, action in routes.items():
            require(isinstance(choice_id, str) and
                    (scene_choices is None or choice_id in scene_choices),
                    "Unknown world-event choice")
            require(isinstance(action, dict) and action.get("kind") in
                    {"continue", "return", "destination"},
                    "Invalid world-event route action")
            kind = action["kind"]
            require(set(action) == ({"kind", "mission"} if kind == "destination"
                                    else {"kind"}), "Invalid world-event route fields")
            if kind == "destination":
                destination = action["mission"]
                require(isinstance(destination, str) and destination in seen
                        and destination not in (source, target),
                        "World detour must name another visible location")
                # Destination must be reachable from either road endpoint
                # through the canonical authored Mission graph.
                graph = _undirected_roads(content, seen)
                require(_connected(graph, source, destination) and
                        _connected(graph, target, destination),
                        "World detour must follow authored roads")
    # A partial world is legal (missions without nodes remain in the regular
    # mission list), but campaigns shown here need a visible starting location.
    for campaign in campaigns:
        start = campaign["start_mission"]
        if any(node["mission"] in _reachable(content, start) for node in nodes):
            require(start in seen, "World is missing a visible campaign start")


def _undirected_roads(content, visible):
    roads = {mid: set() for mid in visible}
    for source in visible:
        for target in content.missions[source].next_missions:
            if target in roads:
                roads[source].add(target)
                roads[target].add(source)
    return roads


def _connected(roads, source, goal):
    if source not in roads or goal not in roads:
        return False
    todo, visited = [source], set()
    while todo:
        at = todo.pop()
        if at == goal:
            return True
        if at not in visited:
            visited.add(at)
            todo.extend(roads[at] - visited)
    return False


def _reachable(content, start):
    todo, seen = [start], set()
    while todo:
        mid = todo.pop()
        if mid in seen:
            continue
        seen.add(mid)
        todo.extend(content.missions[mid].next_missions)
    return seen


def default_world(content, campaigns, *, theme="parchment"):
    """Create an initial layout without changing the actual mission links."""
    require(theme in WORLD_THEMES, "Unknown world theme")
    from .campaign_graph import inspect_graph
    starts = [campaign["start_mission"] for campaign in campaigns]
    graph = inspect_graph(content, starts)
    order = graph["reachable"] + graph["unreachable"]
    require(len(order) <= MAX_WORLD_NODES,
            "Too many missions for a world map")
    columns = 6
    rows = max(1, ceil(len(order) / columns))
    width = WORLD_WIDTH
    height = max(WORLD_HEIGHT, 130 * rows + 80)
    nodes = []
    for i, mid in enumerate(order):
        col, row = i % columns, i // columns
        nodes.append({"mission": mid, "x": 100 + 148 * col,
                      "y": 105 + 120 * row, "region": ""})
    result = {"width": width, "height": height, "theme": theme, "nodes": nodes}
    validate_world(result, content, campaigns)
    return result


def upsert_location(world, content, campaigns, mission_id, pos, *, region=None):
    """Return an entirely new validated map: safe for Studio undo/history."""
    require(bool(world), "Initialize the world map first")
    require(mission_id in content.missions, "Unknown world mission")
    require(isinstance(pos, (tuple, list)) and len(pos) == 2,
            "World position must contain x,y")
    next_world = deepcopy(world)
    node = next((n for n in next_world["nodes"]
                 if n["mission"] == mission_id), None)
    if node is None:
        node = {"mission": mission_id, "x": 0, "y": 0, "region": ""}
        next_world["nodes"].append(node)
    node["x"], node["y"] = pos
    if region is not None:
        node["region"] = region
    validate_world(next_world, content, campaigns)
    return next_world


def remove_location(world, content, campaigns, mission_id):
    """Remove only map artwork, never a Mission or its links."""
    require(bool(world), "World map is not initialized")
    result = deepcopy(world)
    result["nodes"] = [n for n in result["nodes"] if n["mission"] != mission_id]
    validate_world(result, content, campaigns)
    return result


def world_projection(world, content, *, available=(), completed=()):
    """Read-only scene projection. PlayerController still authorizes launches."""
    if not world:
        return {"width": WORLD_WIDTH, "height": WORLD_HEIGHT,
                "theme": "parchment", "nodes": [], "edges": []}
    # Call validation with no campaign constraint for an independent renderer.
    validate_world(world, content, ())
    available, completed = set(available), set(completed)
    positions = {n["mission"]: (n["x"], n["y"]) for n in world["nodes"]}
    nodes = []
    for location in world["nodes"]:
        mid = location["mission"]
        mission = content.missions[mid]
        status = ("completed" if mid in completed else
                  "available" if mid in available else "locked")
        nodes.append({**deepcopy(location), "label": mission.name,
                      "status": status})
    edges = [(src, dest) for src in positions
             for dest in content.missions[src].next_missions
             if dest in positions]
    return {"width": world["width"], "height": world["height"],
            "theme": world["theme"], "nodes": nodes, "edges": edges}


def world_hit_test(projection, position, *, radius=25):
    """Deterministic topmost-node picking shared by Studio and Player."""
    x, y = position
    for node in reversed(projection["nodes"]):
        if (node["x"] - x) ** 2 + (node["y"] - y) ** 2 <= radius ** 2:
            return node["mission"]
    return None
