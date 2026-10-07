"""Event-driven pair/trio progression helpers for Tactical Bonds."""
from itertools import combinations


def pair_key(a: str, b: str) -> str:
    if a == b:
        raise ValueError("A bond needs two distinct units")
    return "|".join(sorted((a, b)))


def _inc(rows: dict[str, dict[str, int]], key: str, stat: str, amount: int = 1):
    stats = rows.setdefault(key, {})
    stats[stat] = stats.get(stat, 0) + amount


def battle_bond_deltas(battle) -> dict[str, dict[str, int]]:
    """Summarize one concluded battle without mutating campaign or battle state."""
    players = sorted(u.id for u in battle.units if u.team == "player")
    player_ids = set(players)
    result: dict[str, dict[str, int]] = {}

    for a, b in combinations(players, 2):
        _inc(result, pair_key(a, b), "missions_together")

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
            sources = sorted(contributors.get(target, set()))
            for a, b in combinations(sources, 2):
                key = pair_key(a, b)
                _inc(result, key, "shared_kills")
                _inc(result, key, f"shared_kill:{target}")
            contributors.pop(target, None)
        elif kind == "tactic":
            members = sorted({uid for uid in event.get("units", []) if uid in player_ids})
            for a, b in combinations(members, 2):
                _inc(result, pair_key(a, b), f"tactic:{event.get('tactic', 'unknown')}")
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


def unlock_rule_met(stats: dict[str, int], rule: dict, *, mission_id: str = "",
                    completed: set[str] | None = None) -> bool:
    """Evaluate a small declarative rule tree; sequence rules come in a later slice."""
    completed = completed or set()
    if "all" in rule:
        return all(unlock_rule_met(stats, child, mission_id=mission_id, completed=completed)
                   for child in rule["all"])
    if "any" in rule:
        return any(unlock_rule_met(stats, child, mission_id=mission_id, completed=completed)
                   for child in rule["any"])
    if "stat" in rule:
        value = stats.get(rule["stat"], 0)
        return value >= rule.get("gte", 1)
    if "mission" in rule:
        return mission_id == rule["mission"]
    if "completed_mission" in rule:
        return rule["completed_mission"] in completed
    return False
