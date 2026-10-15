"""R13.8 — deterministic, read-only AI decisions and combat telemetry.

All observations come from the canonical replay-verified battle_diagnostics
command trace. These are executed actions, not inferred AI alternatives.
Damage/healing amounts are the actual emitted engine events (post mitigation).
"""
from __future__ import annotations

from collections import Counter

from sporebound.encounter_balance6 import ai_decision_analytics
from sporebound.model import require

SCHEMA = 1
MAX_STEPS = 5000
COMBAT_EVENTS = frozenset({"damage", "heal"})
TEAMS = ("player", "enemy", "deployment")


def _amount(event):
    value = event.get("amount")
    require(type(value) is int and 0 <= value <= 1000000,
            "Invalid emitted combat amount")
    return value


def build_combat_visuals(trace):
    """Generate JSON-safe, exact per-step AI/action and HP flow curves.

    Refuses absent/unverified replays, malformed steps and ambiguous combat
    recipients. Heuristic decision warnings are provided by the existing
    canonical analytics; they are *signals* rather than AI correctness proofs.
    No mutation, additional simulation or fabrication of timestamps.
    """
    require(type(trace) is dict and trace.get("kind") == "battle_diagnostics"
            and trace.get("replay_verified") is True
            and type(trace.get("seed")) is int
            and type(trace.get("mission")) is str
            and type(trace.get("digest")) is str
            and type(trace.get("initial")) is dict
            and type(trace.get("steps")) is list
            and len(trace["steps"]) <= MAX_STEPS,
            "R13.8 requires a verified canonical trace (maximum 5000 steps)")
    initial = trace["initial"].get("units")
    require(type(initial) is list, "Invalid initial replay roster")
    roster = {}
    for u in initial:
        require(type(u) is dict and type(u.get("id")) is str
                and type(u.get("team")) is str
                and u["id"] not in roster, "Invalid replay actor identity")
        roster[u["id"]] = u["team"]

    actions = Counter()
    by_team = Counter()
    totals = {"damage": Counter(), "heal": Counter()}
    by_unit = {"damage": Counter(), "heal": Counter()}
    points = [{
        "step": 0,
        "tick": trace["initial"].get("tick", 0),
        "actor": None,
        "action": None,
        "team": None,
        "damage_player": 0, "damage_enemy": 0,
        "heal_player": 0, "heal_enemy": 0,
    }]
    events = []
    for offset, step in enumerate(trace["steps"], 1):
        require(type(step) is dict
                and step.get("index") == offset
                and type(step.get("team")) is str
                and type(step.get("command")) is dict
                and type(step["command"].get("kind")) is str
                and type(step.get("events")) is list
                and type(step.get("after")) is dict,
                "R13.8 encountered an inconsistent canonical step")
        team = step["team"]
        action = step["command"]["kind"]
        actor = step.get("actor")
        require(actor is None or type(actor) is str,
                "Invalid replay actor")
        actions[action] += 1
        by_team[(team, action)] += 1
        frame = step["after"]
        current = frame.get("units")
        require(type(current) is list, "Replay frame units missing")
        for u in current:
            require(type(u) is dict and type(u.get("id")) is str
                    and type(u.get("team")) is str,
                    "Invalid replay unit frame")
            known = roster.setdefault(u["id"], u["team"])
            require(known == u["team"], "Replay actor team changed")
        for e in step["events"]:
            require(type(e) is dict and type(e.get("kind")) is str,
                    "Invalid replay event")
            kind = e["kind"]
            if kind not in COMBAT_EVENTS:
                continue
            count = _amount(e)
            target = e.get("unit")
            require(type(target) is str and target in roster,
                    "Damage or heal event has an unknown target")
            target_team = roster[target]
            totals[kind][target_team] += count
            by_unit[kind][target] += count
            events.append({
                "step": offset, "tick": e.get("tick", frame.get("tick")),
                "kind": kind, "target": target, "team": target_team,
                "source": e.get("source"), "amount": count,
            })
        points.append({
            "step": offset, "tick": frame.get("tick", 0),
            "actor": actor, "action": action, "team": team,
            "damage_player": totals["damage"]["player"],
            "damage_enemy": totals["damage"]["enemy"],
            "heal_player": totals["heal"]["player"],
            "heal_enemy": totals["heal"]["enemy"],
        })

    # Ensure the histogram matches the existing canonical decisions
    # extractor, rather than defining a parallel meaning for AI actions.
    analytic = ai_decision_analytics(trace)
    require(analytic["actions"] == dict(sorted(actions.items()))
            and analytic["team_decisions"]
            == {team + ":" + action: count
                for (team, action), count in sorted(by_team.items())},
            "AI decision telemetry disagrees with canonical diagnostics")
    # Include the existing Battle Diagnostics findings as clickable evidence,
    # not only the movement warnings surfaced by AI analytics.
    diagnostics = trace.get("diagnostics", {})
    require(type(diagnostics) is dict
            and type(diagnostics.get("findings")) is list,
            "Missing canonical replay diagnostics")
    detailed = list(analytic["evidence"])
    for finding in diagnostics["findings"]:
        require(type(finding) is dict and
                type(finding.get("code")) is str and
                type(finding.get("step")) is int,
                "Invalid diagnostic finding")
        detailed.append({
            "step": finding["step"], "actor": finding.get("actor"),
            "team": roster.get(finding.get("actor"), "unknown"),
            "signal": finding["code"],
        })
    detailed.sort(key=lambda item: (item["step"], item["signal"]))
    return {
        "schema": SCHEMA, "kind": "r13_ai_combat_visuals",
        "mission": trace["mission"], "seed": trace["seed"],
        "digest": trace["digest"], "replay_verified": True,
        "steps": len(trace["steps"]),
        "action_totals": dict(sorted(actions.items())),
        "team_actions": [
            {"team": team, "action": action, "count": count}
            for (team, action), count in sorted(by_team.items())
        ],
        "team_damage_received": dict(sorted(totals["damage"].items())),
        "team_healing_received": dict(sorted(totals["heal"].items())),
        "unit_damage_received": dict(sorted(by_unit["damage"].items())),
        "unit_healing_received": dict(sorted(by_unit["heal"].items())),
        "unit_teams": dict(sorted(roster.items())),
        "combat_events": events, "curve": points,
        "signals": analytic["signals"],
        "signal_evidence": detailed[:300],
        "evidence_truncated": len(detailed) > 300,
        "limitations": (
            "Décisions réellement exécutées, pas candidats IA écartés. "
            "Dégâts/soins effectivement émis par le moteur après résolution. "
            "Aucune estimation de durée humaine, DPS réel ou causalité IA."),
    }
