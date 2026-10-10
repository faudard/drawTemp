"""2.7 authored castle integration demo; leaves historical siege fixtures unchanged.

Run: python -m examples.tactical_rpg3_castle
"""
import json

from examples.siege_scenarios import siege_content
from sporebound.bosses3 import boss_preview
from sporebound.engine import Battle
from sporebound.tactical_rpg3 import tactical_rpg_rules


def advanced_castle_content():
    content = siege_content()
    throne = content.missions["castle_throne"]
    next(unit for unit in throne.units if unit.id == "castellan").behavior = "phase_boss"
    trigger = next(t for t in throne.triggers if t["id"] == "castellan_second_phase")
    # Enhance the old phase trigger instead of creating a competing scheduler.
    trigger["actions"].insert(0, {
        "kind": "boss_phase", "unit": "castellan", "phase": 2,
        "form": "Royal Guardian", "footprint": [2, 2],
        "bonuses": {"attack": 4, "defense": 2}})
    content.validate(rules=tactical_rpg_rules())
    return content


def main():
    content = advanced_castle_content()
    rules = tactical_rpg_rules()
    battle = Battle(content, "castle_throne", seed=42, rules=rules)
    if battle.deploying:
        battle.execute({"kind": "start_battle"})
    snapshot = boss_preview(battle, "castellan")
    replay = Battle.replay(battle.recording(), rules=rules)
    assert battle.digest() == replay.digest()
    print(json.dumps({"mission": battle.mission.id, "boss": snapshot,
                      "replay_verified": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
