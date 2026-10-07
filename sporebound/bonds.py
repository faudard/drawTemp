"""Event-driven pair/trio progression helpers for Tactical Bonds."""
from itertools import combinations


def group_key(*members) -> str:
    if len(members) == 1 and not isinstance(members[0], str):
        members = tuple(members[0])
    members = tuple(members)
    if len(members) not in {2, 3} or len(set(members)) != len(members):
        raise ValueError("A bond needs two or three distinct units")
    return "|".join(sorted(members))


def pair_key(a: str, b: str) -> str:
    return group_key(a, b)


def _inc(rows: dict[str, dict[str, int]], key: str, stat: str, amount: int = 1):
    stats = rows.setdefault(key, {})
    stats[stat] = stats.get(stat, 0) + amount


def _bond_groups(members):
    members = sorted(set(members))
    for size in (2, 3):
        if len(members) >= size:
            yield from combinations(members, size)


def battle_bond_deltas(battle) -> dict[str, dict[str, int]]:
    """Summarize one concluded battle without mutating campaign or battle state."""
    players = sorted(u.id for u in battle.units if u.team == "player")
    player_ids = set(players)
    result: dict[str, dict[str, int]] = {}

    for members in _bond_groups(players):
        _inc(result, group_key(members), "missions_together")

    contributors: dict[str, set[str]] = {}
    for event in battle.events:
        kind = event.get("kind")
        if kind == "damage":
            source = event.get("source")
            target = event.get("unit")
            if source in player_ids and target:
                contributors.setdefault(target, set()).add(source)
        elif kind == "downed":
            target = event.get("unit")
            sources = contributors.get(target, set())
            for members in _bond_groups(sources):
                key = group_key(members)
                _inc(result, key, "shared_kills")
                _inc(result, key, f"shared_kill:{target}")
            contributors.pop(target, None)
        elif kind == "tactic":
            members = [uid for uid in event.get("units", []) if uid in player_ids]
            for group in _bond_groups(members):
                _inc(result, group_key(group), f"tactic:{event.get('tactic', 'unknown')}")
        elif kind == "intercept":
            protector, protected = event.get("unit"), event.get("protected")
            if protector in player_ids and protected in player_ids and protector != protected:
                key = pair_key(protector, protected)
                _inc(result, key, "intercepts")
                _inc(result, key, f"intercepts_for:{protected}")
        elif kind == "revive":
            source = event.get("source")
            target = event.get("unit")
            if source in player_ids and target in player_ids and source != target:
                _inc(result, pair_key(source, target), "rescues")
    return result


def merge_bond_stats(target: dict[str, dict[str, int]], delta: dict[str, dict[str, int]]):
    for key, stats in delta.items():
        current = target.setdefault(key, {})
        for stat, amount in stats.items():
            current[stat] = current.get(stat, 0) + amount


def _event_matches(event: dict, spec) -> bool:
    if isinstance(spec, str):
        spec = {"kind": spec}
    return all(event.get(key) == value for key, value in spec.items())


def _sequence_from(events: list[dict], start_index: int, rule: dict,
                   members: list[str] | tuple[str, ...] = ()):
    specs = rule.get("sequence", [])
    first = events[start_index]
    if not specs or not _event_matches(first, specs[0]):
        return None
    matched = [(start_index, first)]
    same_target = rule.get("same_target", False)
    target = first.get("unit") if same_target else None
    first_tick = first.get("tick", 0)
    next_spec = 1
    for index in range(start_index + 1, len(events)):
        event = events[index]
        if rule.get("max_ticks") is not None and event.get("tick", first_tick) - first_tick > rule["max_ticks"]:
            break
        if next_spec >= len(specs):
            break
        if not _event_matches(event, specs[next_spec]):
            continue
        if same_target and event.get("unit") != target:
            continue
        matched.append((index, event))
        next_spec += 1
    if next_spec != len(specs):
        return None
    if rule.get("require_sources") == "all_members":
        sources = {event.get("source") for _, event in matched if event.get("source")}
        if not set(members) <= sources:
            return None
    return matched


def event_sequence_count(events: list[dict], rule: dict,
                         members: list[str] | tuple[str, ...] = ()) -> int:
    """Count non-overlapping ordered matches so repeated secrets cannot reuse events."""
    if not rule.get("sequence"):
        return 0
    count = 0
    cursor = 0
    while cursor < len(events):
        found = None
        for start in range(cursor, len(events)):
            found = _sequence_from(events, start, rule, members)
            if found is not None:
                break
        if found is None:
            break
        count += 1
        cursor = found[-1][0] + 1
    return count


def event_sequence_met(events: list[dict], rule: dict,
                       members: list[str] | tuple[str, ...] = ()) -> bool:
    return event_sequence_count(events, rule, members) >= rule.get("count", 1)


def unlock_rule_met(stats: dict[str, int], rule: dict, *, mission_id: str = "",
                    completed: set[str] | None = None, events: list[dict] | None = None,
                    members: list[str] | tuple[str, ...] = ()) -> bool:
    completed = completed or set()
    if "all" in rule:
        return all(unlock_rule_met(stats, child, mission_id=mission_id, completed=completed,
                                   events=events, members=members) for child in rule["all"])
    if "any" in rule:
        return any(unlock_rule_met(stats, child, mission_id=mission_id, completed=completed,
                                   events=events, members=members) for child in rule["any"])
    if "stat" in rule:
        return stats.get(rule["stat"], 0) >= rule.get("gte", 1)
    if "mission" in rule:
        return mission_id == rule["mission"]
    if "completed_mission" in rule:
        return rule["completed_mission"] in completed
    if "sequence" in rule:
        return event_sequence_met(events or [], rule, members)
    return False


def unlock_progress(stats: dict[str, int], rule: dict, *, mission_id: str = "",
                    completed: set[str] | None = None, events: list[dict] | None = None,
                    members: list[str] | tuple[str, ...] = ()) -> float:
    """Return 0..1 discovery progress for codex/UI without mutating state."""
    completed = completed or set()
    if "all" in rule:
        values = [unlock_progress(stats, child, mission_id=mission_id, completed=completed,
                                  events=events, members=members) for child in rule["all"]]
        return sum(values) / len(values)
    if "any" in rule:
        return max(unlock_progress(stats, child, mission_id=mission_id, completed=completed,
                                   events=events, members=members) for child in rule["any"])
    if "stat" in rule:
        goal = rule.get("gte", 1)
        return min(1.0, stats.get(rule["stat"], 0) / goal)
    if "mission" in rule:
        return 1.0 if mission_id == rule["mission"] else 0.0
    if "completed_mission" in rule:
        return 1.0 if rule["completed_mission"] in completed else 0.0
    if "sequence" in rule:
        goal = rule.get("count", 1)
        return min(1.0, event_sequence_count(events or [], rule, members) / goal)
    return 0.0
