"""R25.B: strict scene connections over canonical Content/GameProject references.

SceneRouter is an immutable reader of authored routes. GameSession remains the
sole owner of cursor, campaign, battle and replay/checkpoint state.
"""
from copy import deepcopy

from .model import require
from .narrative import _condition, matches


SCHEMA_VERSION = 1
MAX_ROUTES = 512
MAX_HISTORY = 4096


def _id(value):
    return (type(value) is str and 0 < len(value) <= 64
            and all(c.isalnum() or c in "_-" for c in value))


def _exploration_spawn(project, scene_id, spawn):
    stage = project.exploration[scene_id]
    return (type(spawn) is list and len(spawn) == 2
            and all(type(v) is int for v in spawn)
            and 0 <= spawn[0] < stage["width"]
            and 0 <= spawn[1] < stage["height"]
            and spawn not in stage["blocked"])


def _tactical_spawn(content, mission_id, spawn):
    mission = content.missions[mission_id]
    if not (type(spawn) is list and len(spawn) == 2
            and all(type(v) is int for v in spawn)
            and mission.board.contains(tuple(spawn))
            and not mission.board.tile(tuple(spawn)).blocked):
        return False
    # This release does not change authored Battle deployment or replay.
    # A portal into CT must designate a position already used by a hero;
    # later deployment overrides need their own versioned tactical contract.
    return any(unit.team == "player" and list(unit.pos) == spawn
               for unit in mission.units)


def validate_scene_routes(raw, content, project):
    require(type(raw) is dict, "Scene routes must be an object")
    if not raw:
        return
    require(set(raw) == {"version", "start", "links"}
            and type(raw["version"]) is int
            and raw["version"] == SCHEMA_VERSION,
            "Invalid or unsupported scene route schema")
    start = raw["start"]
    require(_id(start) and start in project.exploration,
            "Route start must be an existing exploration scene")
    require(type(raw["links"]) is list
            and len(raw["links"]) <= MAX_ROUTES,
            "Invalid scene link list")
    known = set(project.exploration) | set(content.missions)
    require(not set(project.exploration).intersection(content.missions),
            "Ambiguous tactical/exploration scene identity")
    ids = set()
    for row in raw["links"]:
        require(type(row) is dict
                and {"id", "source", "destination", "spawn"} <= set(row)
                <= {"id", "source", "destination", "spawn", "when"},
                "Invalid scene link fields")
        ident, source, dest = row["id"], row["source"], row["destination"]
        require(_id(ident) and ident not in ids,
                "Duplicate or invalid scene link identity")
        ids.add(ident)
        require(type(source) is str and source in known
                and type(dest) is str and dest in known
                and source != dest, "Unknown or cyclic self scene route")
        if dest in content.missions:
            require(_tactical_spawn(content, dest, row["spawn"]),
                    "Tactical destination must use an authored hero spawn")
        else:
            require(_exploration_spawn(project, dest, row["spawn"]),
                    "Destination spawn is out of bounds or blocked")
        if "when" in row:
            _condition(row["when"], content)
    # This is connectivity validation, not a declaration that every path
    # is necessarily reachable under dynamic narrative conditions.
    reachable = {start}
    while True:
        extended = reachable | {link["destination"] for link in raw["links"]
                                if link["source"] in reachable}
        if extended == reachable:
            break
        reachable = extended
    require(all(row["source"] in reachable for row in raw["links"]),
            "Scene route contains an unreachable source")


class SceneRouter:
    """Validated, read-only route map; persistence belongs to GameSession."""

    def __init__(self, raw, content, project):
        validate_scene_routes(raw, content, project)
        self.raw = deepcopy(raw)
        self.content = content
        self.project = project
        self.links = {row["id"]: row for row in raw.get("links", [])}

    @property
    def enabled(self):
        return bool(self.raw)

    @property
    def start(self):
        return self.raw["start"] if self.enabled else None

    def destination(self, current, link_id, progress):
        require(self.enabled, "Scene routing is not enabled for this project")
        require(type(link_id) is str and link_id in self.links,
                "Unknown scene transition")
        route = self.links[link_id]
        require(route["source"] == current, "Scene transition starts elsewhere")
        if "when" in route:
            require(matches(route["when"], progress),
                    "Scene transition prerequisites are not satisfied")
        return deepcopy(route)

    def validate_checkpoint(self, data, *, mode, battle):
        require(self.enabled and type(data) is dict
                and set(data) == {"version", "current", "history"}
                and type(data["version"]) is int
                and data["version"] == SCHEMA_VERSION
                and type(data["history"]) is list
                and len(data["history"]) <= MAX_HISTORY,
                "Invalid scene route checkpoint")
        current = self.start
        for ident in data["history"]:
            require(type(ident) is str and ident in self.links,
                    "Checkpoint contains an unknown scene route")
            link = self.links[ident]
            require(link["source"] == current,
                    "Checkpoint contains a disconnected scene route")
            current = link["destination"]
        require(data["current"] == current,
                "Scene route cursor does not match its history")
        if mode == "battle":
            require(battle is not None and battle.mission.id == current
                    and current in self.content.missions,
                    "Scene route tactical encounter mismatch")
        elif mode == "campaign":
            require(battle is None, "Campaign route contains live tactical state")
        else:
            raise ValueError("Scene routes do not support multi-front sessions yet")
        return current


__all__ = ["SceneRouter", "validate_scene_routes", "MAX_HISTORY"]
