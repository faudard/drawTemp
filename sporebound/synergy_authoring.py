"""Transactional authoring and bounded visual trees for tactical synergy unlocks.

Uses Content.tactic_unlocks and sporebound.bonds evaluation unchanged. Tree paths
are editor-only; saved conditions are ordinary all/any/stat/mission/sequence dicts.
"""
from copy import deepcopy

from .bonds import unlock_progress, unlock_rule_met, group_key
from .model import Content, require
from .rules import default_rules

HINT_STAGES = ("hidden", "clue", "near", "unlocked")
STAT_PRESETS = ("missions_together", "shared_kills", "rescues", "intercepts")
EVENT_FIELDS = ("kind", "source", "unit", "status", "mode", "tactic")


def _validated(data):
    return Content.from_dict(data).to_dict()


def _ids(data):
    return {u["id"] for m in data["missions"] for u in m["units"]
            if u["team"] == "player"}


def _rule(data, index):
    rules = data.get("tactic_unlocks", [])
    require(type(index) is int and 0 <= index < len(rules), "Unknown synergy")
    return rules[index]


def _check(data, tactic, members):
    available = default_rules().tactics
    require(isinstance(tactic, str) and tactic in available, "Unknown tactic")
    require(isinstance(members, list) and
            all(isinstance(m, str) for m in members) and
            len(members) in (2, 3) and len(set(members)) == len(members),
            "A synergy requires two or three distinct members")
    require(len(members) == available.get(tactic).arity, "Tactic arity mismatch")
    require(set(members) <= _ids(data), "Unknown player member")


def _ensure_unique(data, tactic, members, *, except_index=None):
    key = (tactic, group_key(members))
    for index, record in enumerate(data.get("tactic_unlocks", [])):
        if index != except_index:
            require((record["id"], group_key(record["members"])) != key,
                    "This group already has an unlock for the tactic")


def leaf(kind, *, stat="shared_kills", threshold=1, mission="",
         sequence=None, count=1, max_ticks=10,
         same_target=False, require_sources=False):
    """Create a predicate with the exact shape accepted by Content and bonds."""
    if kind == "stat":
        require(isinstance(stat, str) and bool(stat.strip()), "Stat name required")
        require(type(threshold) is int and 1 <= threshold <= 1000000,
                "Statistic threshold must be 1..1000000")
        return {"stat": stat.strip(), "gte": threshold}
    if kind in ("mission", "completed_mission"):
        require(isinstance(mission, str) and bool(mission),
                "Choose a mission")
        return {kind: mission}
    if kind == "sequence":
        require(isinstance(sequence, list) and len(sequence) >= 1
                and all(isinstance(spec, dict) and spec.get("kind")
                        for spec in sequence), "Sequence needs at least one event")
        require(type(count) is int and 1 <= count <= 1000,
                "Sequence repetitions must be 1..1000")
        require(type(max_ticks) is int and 1 <= max_ticks <= 100000,
                "Sequence time window must be 1..100000 ticks")
        require(type(same_target) is bool and type(require_sources) is bool,
                "Invalid sequence filters")
        result = {"sequence": deepcopy(sequence), "count": count,
                  "max_ticks": max_ticks, "same_target": same_target}
        if require_sources:
            result["require_sources"] = "all_members"
        return result
    raise ValueError("Unknown synergy predicate")


def event_spec(kind, **details):
    """Only authored values are fields matched by the existing event evaluator."""
    require(isinstance(kind, str) and bool(kind.strip()),
            "Event kind required")
    require(set(details) <= set(EVENT_FIELDS) - {"kind"},
            "Unknown event matcher field")
    require(all(isinstance(value, str) and bool(value.strip())
                for value in details.values()), "Invalid event matcher value")
    return {"kind": kind.strip(), **deepcopy(details)}


def _path(path):
    require(isinstance(path, (tuple, list)) and len(path) <= 12,
            "Invalid condition tree path")
    for item in path:
        require(isinstance(item, (tuple, list)) and len(item) == 2
                and item[0] in ("all", "any") and type(item[1]) is int
                and item[1] >= 0, "Invalid condition node path")
    return tuple(tuple(item) for item in path)


def _node(root, path):
    current = root
    for key, index in _path(path):
        require(isinstance(current, dict) and
                isinstance(current.get(key), list) and
                index < len(current[key]), "Condition path no longer exists")
        current = current[key][index]
    return current


def _label(node):
    if "all" in node:
        return "ET — toutes les conditions"
    if "any" in node:
        return "OU — une condition suffit"
    if "stat" in node:
        return str(node["stat"]) + " ≥ " + str(node.get("gte", 1))
    if "mission" in node:
        return "Mission actuelle : " + node["mission"]
    if "completed_mission" in node:
        return "Mission terminée : " + node["completed_mission"]
    if "sequence" in node:
        names = [item if isinstance(item, str) else item.get("kind", "?")
                 for item in node["sequence"]]
        return "Séquence : " + " → ".join(names) + (
            " (×" + str(node.get("count", 1)) + ")")
    return "Condition inconnue"


def rows(rule, *, max_nodes=300):
    """Flatten one rule to stable visual rows, never serializing tuple paths."""
    require(type(max_nodes) is int and 1 <= max_nodes <= 1000, "Invalid node limit")
    result = []

    def visit(node, path, depth):
        require(isinstance(node, dict), "Malformed unlock condition")
        if len(result) >= max_nodes:
            return
        result.append({"path": path, "depth": depth, "label": _label(node),
                       "kind": next(iter(node)), "rule": deepcopy(node)})
        if "all" in node or "any" in node:
            key = "all" if "all" in node else "any"
            if depth < 12:
                for index, child in enumerate(node[key]):
                    visit(child, path + ((key, index),), depth + 1)
    visit(rule, (), 0)
    return result


def change_tree(rule, action, *, path=(), value=None, operator="all"):
    """Pure replacement/AND/OR wrapping/append/delete of one unlock subtree."""
    require(action in ("replace", "wrap", "append", "delete"),
            "Unknown unlock tree operation")
    require(operator in ("all", "any"), "Unknown boolean operator")
    path = _path(path)
    root = deepcopy(rule)
    require(isinstance(root, dict), "Invalid unlock root")
    selected = _node(root, path)
    if action in ("replace", "append"):
        require(isinstance(value, dict) and bool(value), "Select a predicate")
    if action == "wrap":
        substitute = {operator: [deepcopy(selected)]}
    elif action == "replace":
        substitute = deepcopy(value)
    elif action == "append":
        key = "all" if "all" in selected else "any" if "any" in selected else ""
        require(key, "Select an AND/OR group before adding")
        require(len(selected[key]) < 20, "Group contains too many predicates")
        selected[key].append(deepcopy(value))
        return root
    else:
        if not path:
            raise ValueError("The root unlock condition cannot be deleted")
        parent = _node(root, path[:-1])
        key, index = path[-1]
        require(len(parent[key]) > 1, "An AND/OR group cannot be empty")
        del parent[key][index]
        return root
    if not path:
        return substitute
    parent = _node(root, path[:-1])
    key, index = path[-1]
    parent[key][index] = substitute
    return root


def save_unlock(data, tactic, members, condition, *, hints=None, index=None):
    """Create or modify one unlock atomically, validated by the actual engine."""
    require(isinstance(data, dict), "Invalid content document")
    _check(data, tactic, members)
    _ensure_unique(data, tactic, members, except_index=index)
    require(isinstance(condition, dict) and bool(condition),
            "Choose a nonempty unlock condition")
    require(hints is None or (isinstance(hints, dict)
            and set(hints) <= set(HINT_STAGES)), "Invalid discovery hints")
    new = deepcopy(data)
    row = {"id": tactic, "members": list(members),
           "unlock": deepcopy(condition)}
    if hints:
        row["hints"] = deepcopy(hints)
    if index is None:
        new.setdefault("tactic_unlocks", []).append(row)
    else:
        _rule(new, index)
        new["tactic_unlocks"][index] = row
    return _validated(new)


def delete_unlock(data, index):
    new = deepcopy(data)
    _rule(new, index)
    del new["tactic_unlocks"][index]
    return _validated(new)


def preview(data, index, *, stats=None, mission_id="", completed=(), events=()):
    """Read-only preview through the same bonds functions as the campaign."""
    entry = _rule(data, index)
    stats = {} if stats is None else stats
    require(isinstance(stats, dict) and all(isinstance(k, str)
            and type(v) is int and v >= 0 for k, v in stats.items()),
            "Preview stats must be nonnegative integers")
    require(isinstance(mission_id, str) and
            isinstance(completed, (tuple, list, set)) and
            all(isinstance(m, str) for m in completed),
            "Invalid mission preview state")
    require(isinstance(events, (tuple, list)) and
            all(isinstance(item, dict) for item in events),
            "Invalid preview combat events")
    requirement = entry["unlock"]
    kw = dict(mission_id=mission_id, completed=set(completed),
              events=list(events), members=entry["members"])
    return {"met": unlock_rule_met(stats, requirement, **kw),
            "progress": unlock_progress(stats, requirement, **kw),
            "tactic": entry["id"], "members": list(entry["members"])}
