"""Validated, headless narrative exploration stages.

Exploration uses the existing Campaign.story_flags checkpoint instead of
inventing a second save file. Its commands are deterministic, atomic and
independent of Tk or tactical Battle.
"""
from collections import deque
from copy import deepcopy
from hashlib import sha256

from .model import require


def _cell(value, width, height):
    return (isinstance(value, (list, tuple)) and len(value) == 2
            and all(type(n) is int for n in value)
            and 0 <= value[0] < width and 0 <= value[1] < height)


def _key(scene_id, suffix):
    """Short stable flag names even when narrative scene IDs use 64 chars."""
    return "ex_" + sha256(scene_id.encode("utf-8")).hexdigest()[:12] + "_" + suffix


def validate_exploration(raw, story):
    require(isinstance(raw, dict), "Exploration must be an object")
    scenes = {s["id"] for s in story.get("scenes", [])}
    for sid, stage in raw.items():
        require(isinstance(sid, str) and sid in scenes,
                "Exploration references an unknown narrative scene")
        require(isinstance(stage, dict) and set(stage) ==
                {"title", "theme", "width", "height", "start", "blocked", "interactions"},
                f"{sid}: invalid exploration fields")
        require(isinstance(stage["title"], str) and 0 < len(stage["title"]) <= 120,
                f"{sid}: invalid title")
        require(stage["theme"] in ("fields", "village", "forest", "stone"),
                f"{sid}: unknown stage theme")
        w, h = stage["width"], stage["height"]
        require(type(w) is int and type(h) is int and 3 <= w <= 32 and 3 <= h <= 32,
                f"{sid}: stage dimensions")
        start = stage["start"]
        require(_cell(start, w, h), f"{sid}: invalid starting position")
        blocked = stage["blocked"]
        require(isinstance(blocked, list) and len(blocked) <= w * h,
                f"{sid}: invalid obstacle list")
        require(all(_cell(c, w, h) for c in blocked), f"{sid}: invalid obstacle")
        solid = {tuple(c) for c in blocked}
        require(len(solid) == len(blocked) and tuple(start) not in solid,
                f"{sid}: overlapping obstacles/start")
        points = stage["interactions"]
        require(isinstance(points, list) and 1 <= len(points) <= 12,
                f"{sid}: expected 1..12 interactions")
        ids, exits = set(), []
        for point in points:
            require(isinstance(point, dict) and set(point) ==
                    {"id", "title", "text", "pos", "required", "exit"},
                    f"{sid}: invalid interaction")
            ident = point["id"]
            require(isinstance(ident, str) and 0 < len(ident) <= 24
                    and all(c.isalnum() or c == "_" for c in ident)
                    and ident not in ids, f"{sid}: duplicate/invalid interaction id")
            ids.add(ident)
            require(isinstance(point["title"], str) and 0 < len(point["title"]) <= 100
                    and isinstance(point["text"], str) and 0 < len(point["text"]) <= 1000,
                    f"{sid}: invalid interaction text")
            require(type(point["required"]) is bool and type(point["exit"]) is bool,
                    f"{sid}: invalid required/exit")
            require(_cell(point["pos"], w, h) and tuple(point["pos"]) not in solid,
                    f"{sid}: invalid interaction position")
            if point["exit"]:
                exits.append(point)
                require(not point["required"], f"{sid}: exit cannot be required")
        require(len(exits) == 1, f"{sid}: exactly one exit required")
        # All hotspots must be reachable (or adjacent to a reachable cell);
        # validate before allowing a project to be saved.
        queue, reached = deque([tuple(start)]), {tuple(start)}
        while queue:
            x, y = queue.popleft()
            for xy in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if (0 <= xy[0] < w and 0 <= xy[1] < h
                        and xy not in reached and xy not in solid):
                    reached.add(xy)
                    queue.append(xy)
        require(all(any(abs(px - x) + abs(py - y) <= 1 for x, y in reached)
                    for px, py in (point["pos"] for point in points)),
                f"{sid}: unreachable interaction")


class Exploration:
    def __init__(self, raw, story):
        validate_exploration(raw, story)
        self.scenes = deepcopy(raw)

    def state(self, progress, scene_id):
        stage = self.scenes.get(scene_id)
        if stage is None:
            return None
        original = stage["start"]
        position = progress.story_flags.get(_key(scene_id, "pos"),
                                            ",".join(map(str, original)))
        require(isinstance(position, str), "Invalid exploration position")
        try:
            parts = position.split(",")
            require(len(parts) == 2, "Invalid exploration position")
            xy = [int(parts[0]), int(parts[1])]
        except (ValueError, IndexError) as exc:
            raise ValueError("Invalid exploration position") from exc
        require(_cell(xy, stage["width"], stage["height"]) and
                xy not in stage["blocked"], "Invalid saved exploration position")
        result = deepcopy(stage)
        result["scene_id"] = scene_id
        result["position"] = xy
        result["completed"] = progress.story_flags.get(_key(scene_id, "done"), False)
        require(type(result["completed"]) is bool, "Invalid exploration completion")
        for point in result["interactions"]:
            value = progress.story_flags.get(_key(scene_id, point["id"]), False)
            require(type(value) is bool, "Invalid exploration interaction state")
            point["visited"] = value
        return result

    def move(self, progress, scene_id, dx, dy):
        stage = self.state(progress, scene_id)
        require(stage is not None and not stage["completed"], "No active exploration")
        require(type(dx) is int and type(dy) is int
                and abs(dx) + abs(dy) == 1, "Move one cardinal cell")
        x, y = stage["position"]
        next_pos = [x + dx, y + dy]
        require(_cell(next_pos, stage["width"], stage["height"])
                and next_pos not in stage["blocked"], "Exploration route blocked")
        progress.story_flags[_key(scene_id, "pos")] = ",".join(map(str, next_pos))
        return self.state(progress, scene_id)

    def interact(self, progress, scene_id, point_id):
        stage = self.state(progress, scene_id)
        require(stage is not None and not stage["completed"], "No active exploration")
        point = next((p for p in stage["interactions"] if p["id"] == point_id), None)
        require(point is not None, "Unknown exploration interaction")
        require(sum(abs(a - b) for a, b in zip(stage["position"], point["pos"])) <= 1,
                "Move closer to interact")
        if point["exit"]:
            require(all(p["visited"] for p in stage["interactions"] if p["required"]),
                    "Explore the required memories before leaving")
            progress.story_flags[_key(scene_id, "done")] = True
        else:
            progress.story_flags[_key(scene_id, point_id)] = True
        return {"id": point_id, "title": point["title"], "text": point["text"],
                "finished": point["exit"]}
