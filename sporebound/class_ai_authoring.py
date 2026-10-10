"""2.5.3.3 class progression, talent DAG and tactical AI authoring.

Pure transformations of Content v1; existing rules and save structure remain
authoritative. The graph visualizations don't introduce runtime rules.
"""
from copy import deepcopy

from .authoring import _identifier, _mission
from .builds3 import STATS as TALENT_STATS
from .model import Content, require
from .rules import default_rules

ROLES = ("medic", "healer", "protector", "leader", "ranged", "flanker",
         "siege", "scout")
BONUS_NAMES = tuple(sorted(TALENT_STATS))


def _content(data):
    return Content.from_dict(data).to_dict()


def _job(data, job_id):
    job = data.get("jobs", {}).get(job_id)
    require(job is not None, "Unknown job")
    return job


def _talent(data, job_id, talent_id):
    talents = _job(data, job_id).get("talents", {})
    require(talent_id in talents, "Unknown talent")
    return talents[talent_id]


def _validate_job_dag(data):
    jobs = data.get("jobs", {})
    seen, active = set(), set()
    def walk(job_id):
        require(job_id not in active, "Cyclic job prerequisites")
        if job_id in seen:
            return
        active.add(job_id)
        parent = jobs[job_id].get("requires", "")
        if parent:
            require(parent in jobs, "Unknown job prerequisite")
            walk(parent)
        active.remove(job_id)
        seen.add(job_id)
    for job_id in sorted(jobs):
        walk(job_id)


def _validated(data):
    _validate_job_dag(data)
    return _content(data)


def link_job(data, job_id, prerequisite, level=1):
    """Change a class prerequisite; reject cycles and missing jobs."""
    require(type(level) is int and 1 <= level <= 20,
            "Required class level must be 1..20")
    require(isinstance(prerequisite, str), "Invalid parent job")
    new = deepcopy(data)
    job = _job(new, job_id)
    require(prerequisite != job_id, "Class cannot require itself")
    job["requires"] = prerequisite
    job["requires_level"] = level
    return _validated(new)


def job_graph(data):
    """Deterministic layered DAG of jobs and their prerequisite links."""
    _validate_job_dag(data)
    jobs = data.get("jobs", {})
    depths = {}
    def depth(jid):
        if jid not in depths:
            parent = jobs[jid].get("requires", "")
            depths[jid] = depth(parent) + 1 if parent else 0
        return depths[jid]
    for jid in sorted(jobs):
        depth(jid)
    grouped = {}
    for jid, dep in sorted(depths.items()):
        grouped.setdefault(dep, []).append(jid)
    nodes = []
    for dep, keys in sorted(grouped.items()):
        for row, jid in enumerate(keys):
            spec = jobs[jid]
            nodes.append({"id": jid, "label": spec.get("name", jid),
                          "requires": spec.get("requires", ""),
                          "required_level": spec.get("requires_level", 1),
                          "depth": dep, "x": 70 + 250 * dep,
                          "y": 75 + 125 * row})
    edges = [{"from": j.get("requires"), "to": jid}
             for jid, j in sorted(jobs.items()) if j.get("requires")]
    return {"nodes": nodes, "edges": edges,
            "width": 310 + 250 * max(depths.values(), default=0),
            "height": 170 + 125 * max((len(group) for group in grouped.values()),
                                      default=0)}


def talent_graph(data, job_id):
    """Deterministic DAG projection from the runtime talent schema."""
    job = _job(data, job_id)
    specs = job.get("talents", {})
    require(isinstance(specs, dict), "Invalid talent data")
    depths, visiting = {}, set()
    def depth(tid):
        if tid in depths:
            return depths[tid]
        require(tid not in visiting, "Cyclic talent prerequisites")
        visiting.add(tid)
        deps = specs[tid].get("requires", [])
        require(all(dep in specs for dep in deps), "Unknown talent requirement")
        result = 1 + max((depth(parent) for parent in deps), default=-1)
        visiting.remove(tid)
        depths[tid] = result
        return result
    for tid in sorted(specs):
        depth(tid)
    grouped = {}
    for tid, d in sorted(depths.items()):
        grouped.setdefault(d, []).append(tid)
    nodes = []
    for d, keys in sorted(grouped.items()):
        for row, tid in enumerate(keys):
            spec = specs[tid]
            nodes.append({"id": tid, "jp": spec.get("jp", 1),
                          "exclusive": spec.get("exclusive", ""),
                          "requires": list(spec.get("requires", [])),
                          "depth": d, "x": 70 + d * 235,
                          "y": 75 + row * 130})
    edges = [{"from": source, "to": tid}
             for tid, spec in sorted(specs.items())
             for source in spec.get("requires", [])]
    return {"job_id": job_id, "nodes": nodes, "edges": edges,
            "width": 300 + 235 * max(depths.values(), default=0),
            "height": 170 + 130 * max((len(group) for group in grouped.values()),
                                      default=0)}


def make_talent(*, jp=1, requires=(), exclusive="", bonuses=None, skills=()):
    require(type(jp) is int and 1 <= jp <= 20, "Talent JP must be 1..20")
    require(isinstance(requires, (list, tuple))
            and all(isinstance(k, str) for k in requires),
            "Invalid talent prerequisite IDs")
    require(isinstance(exclusive, str), "Invalid specialization")
    require(isinstance(skills, (list, tuple)) and
            all(isinstance(s, str) for s in skills), "Invalid talent skills")
    require(isinstance(bonuses, dict) or bonuses is None,
            "Invalid talent bonuses")
    result = {"jp": jp, "requires": list(requires),
              "exclusive": exclusive.strip(),
              "bonuses": deepcopy(bonuses or {}), "skills": list(skills)}
    require(set(result["bonuses"]) <= TALENT_STATS and
            all(type(v) is int and 0 <= v <= 100 for v in result["bonuses"].values()),
            "Invalid talent stat bonus")
    return result


def save_talent(data, job_id, talent_id, spec, *, creating=False):
    _identifier(talent_id, "Talent id")
    require(isinstance(spec, dict), "Invalid talent")
    new = deepcopy(data)
    talents = _job(new, job_id).setdefault("talents", {})
    require((talent_id not in talents) if creating else (talent_id in talents),
            "Talent already exists" if creating else "Unknown talent")
    talents[talent_id] = deepcopy(spec)
    return _validated(new)


def delete_talent(data, job_id, talent_id):
    new = deepcopy(data)
    talents = _job(new, job_id).setdefault("talents", {})
    _talent(new, job_id, talent_id)
    require(not any(talent_id in spec.get("requires", ())
                    for tid, spec in talents.items() if tid != talent_id),
            "Talent required by another talent")
    del talents[talent_id]
    return _validated(new)


def parse_cells(text):
    """Human-friendly comma/semicolon-separated points, no arbitrary eval."""
    require(isinstance(text, str), "Invalid route")
    if not text.strip():
        return []
    points = []
    for token in text.split(";"):
        parts = [p.strip() for p in token.split(",")]
        require(len(parts) == 2 and all(p.isdecimal() for p in parts),
                "Waypoints must be x,y separated by semicolons")
        points.append([int(parts[0]), int(parts[1])])
    require(len(points) >= 2 and len(set(tuple(p) for p in points)) == len(points),
            "Patrol requires two or more distinct waypoints")
    return points


def validate_route(data, mission_id, cells):
    m = _mission(data, mission_id)
    require(m is not None, "Unknown mission")
    require(isinstance(cells, list), "Invalid waypoints")
    width, height = m["board"]["width"], m["board"]["height"]
    blocked = {tuple(t["pos"]) for t in m["board"].get("tiles", [])
               if t.get("blocked", False)}
    for x, y in cells:
        require(type(x) is int and type(y) is int
                and 0 <= x < width and 0 <= y < height
                and (x,y) not in blocked, "Patrol waypoint outside map or blocked")


def set_unit_ai(data, mission_id, unit_id, *, behavior="tactical",
                roles=(), route=()):
    """Use default deterministic tactical rules with an optional patrol.

    coordinated AI is an opt-in ruleset; do not silently author it into
    Content validated by the default battle engine.
    """
    require(behavior == "tactical",
            "Only standard tactical AI is portable; coordinated AI needs opt-in rules")
    require(isinstance(roles, (list, tuple))
            and all(isinstance(r, str) for r in roles)
            and len(set(roles)) == len(roles), "Duplicate or invalid AI roles")
    require(isinstance(route, (list, tuple)), "Invalid patrol route")
    cells = [list(point) for point in route]
    require(not cells or len(cells) >= 2, "Patrol requires at least two waypoints")
    require(len({tuple(x) for x in cells}) == len(cells),
            "Duplicate patrol waypoint")
    validate_route(data, mission_id, cells)
    new = deepcopy(data)
    m = _mission(new, mission_id)
    actor = next((u for u in m["units"] if u["id"] == unit_id), None)
    require(actor is not None, "Unknown actor")
    actor["behavior"] = behavior
    actor["tags"] = list(roles)
    actor["patrol_route"] = cells
    return _validated(new)


def ai_preview(data, mission_id, unit_id):
    """Read-only editable policy summary (not a fabricated battle forecast)."""
    m = _mission(data, mission_id)
    require(m is not None, "Unknown mission")
    actor = next((u for u in m["units"] if u["id"] == unit_id), None)
    require(actor is not None, "Unknown actor")
    route = actor.get("patrol_route", [])
    return {"unit_id": unit_id, "behavior": actor.get("behavior", "tactical"),
            "roles": list(actor.get("tags", [])),
            "waypoints": deepcopy(route), "mode": "patrol" if route else "tactical",
            "ruleset": "standard", "coordinated_active": False}
