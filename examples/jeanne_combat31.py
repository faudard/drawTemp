"""Jeanne (alternate history) — tactical breach of the castle courtyard.

Small, importable siege encounter focused on CT, spear lanes, support,
directional melee pressure and visible telegraphs. Standalone Python only.

    python -m examples.jeanne_combat31 --preview
    python -m examples.jeanne_combat31 --export /tmp/jeanne_siege.json
    python -m examples.jeanne_combat31 --compare

The exported Content can be opened in the Studio; no handcrafted JSON needed.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from examples.siege_scenarios import siege_content
from sporebound.balance3 import compare_compositions, evaluate
from sporebound.engine import Battle
from sporebound.model import Board, Effect, Skill, Tile, Unit
from sporebound.tactical_intents import tactical_intents
from sporebound.tactical_rpg3 import tactical_rpg_rules


MISSION = "jeanne_courtyard_breach"
SEEDS = (1, 7, 42, 99)


def jeanne_siege_content(*, coordinated=True):
    """Build a deterministic, editor-exportable mission alongside castle fixtures.

    Enemy coordination is changed via existing unit tags only: identical
    actors, stats, map, objectives and AI behavior in both A/B variants.
    """
    content = siege_content()
    courtyard = deepcopy(content.missions["castle_courtyard"])
    courtyard.id = MISSION
    courtyard.name = "Jeanne — la cour intérieure (brèche)"
    courtyard.objective = "eliminate"
    courtyard.deployment = []
    courtyard.goal = []
    courtyard.triggers = []
    courtyard.objects = []
    courtyard.reward = 140
    courtyard.board = Board(12, 8, {
        (6, 0): Tile(blocked=True),
        (6, 1): Tile(blocked=True),
        (6, 6): Tile(blocked=True),
        (6, 7): Tile(blocked=True),
        (5, 2): Tile(cover=20),
        (5, 5): Tile(cover=20),
        (8, 2): Tile(cover=25),
        (8, 5): Tile(cover=25),
        (9, 1): Tile(height=1),
    })
    content.skills["field_heal"] = Skill(
        "field_heal", "Pansement de campagne", [Effect("heal", 12)],
        cost=3, range=3, target="ally", accuracy=100)
    content.skills["signal_flame"] = Skill(
        "signal_flame", "Flamme annoncée", [Effect("damage", 4)],
        cost=3, range=5, radius=1, target="ground",
        magical=True, cast_ticks=3, accuracy=90)

    def roles(*tags):
        return list(tags) if coordinated else []

    courtyard.units = [
        Unit("jeanne", "Jeanne", "player", (2, 3), max_hp=90, hp=90,
             attack=10, weapon_power=4, defense=2, speed=15, move=4,
             facing=(1, 0), tactics=["pincer"]),
        Unit("ecuyer", "Écuyer de Jeanne", "player", (2, 4),
             max_hp=68, hp=68, attack=8, weapon_power=3, defense=2,
             speed=12, weapon="spear", move=4, facing=(1, 0),
             tactics=["pincer"]),
        Unit("arbaletriere", "Arbalétrière", "player", (1, 2),
             max_hp=52, hp=52, attack=7, weapon_power=3, defense=1,
             speed=13, weapon="ranged", attack_range=5, min_range=2,
             facing=(1, 0)),
        Unit("chirurgien", "Chirurgien de camp", "player", (1, 5),
             max_hp=48, hp=48, attack=5, weapon_power=2, speed=11,
             skills=["field_heal"], facing=(1, 0)),
        # First two pikes guard the broken arch; their adjacent formation
        # can be defeated by a flank attack, ranged control or displacement.
        Unit("lance_nord", "Lancier du rempart", "enemy", (7, 2),
             max_hp=56, hp=56, attack=7, weapon_power=3,
             defense=2, speed=12, weapon="spear", facing=(-1, 0),
             tags=roles("squad:pikeman"), behavior="coordinated"),
        Unit("lance_sud", "Lancier de la cour", "enemy", (7, 3),
             max_hp=56, hp=56, attack=7, weapon_power=3,
             defense=2, speed=12, weapon="spear", facing=(-1, 0),
             tags=roles("squad:pikeman"), behavior="coordinated"),
        Unit("chevalier", "Chevalier de la porte", "enemy", (7, 4),
             max_hp=85, hp=85, attack=8, weapon_power=4,
             defense=3, speed=10, facing=(-1, 0),
             tags=roles("squad:vanguard"), behavior="coordinated"),
        Unit("archer", "Archer des remparts", "enemy", (9, 2),
             max_hp=42, hp=42, attack=6, weapon_power=3,
             defense=0, speed=11, weapon="ranged",
             attack_range=5, min_range=2, facing=(-1, 0),
             tags=roles("squad:archer"), behavior="coordinated"),
        Unit("soigneur", "Soigneur de la garnison", "enemy", (10, 4),
             max_hp=39, hp=39, attack=4, weapon_power=2,
             defense=0, speed=11, skills=["field_heal"],
             facing=(-1, 0), tags=roles("squad:medic"),
             behavior="coordinated"),
        Unit("officier", "Officier du château", "enemy", (10, 5),
             max_hp=51, hp=51, attack=7, weapon_power=3,
             defense=2, speed=12, skills=["signal_flame"],
             facing=(-1, 0), tags=roles("squad:officer"),
             behavior="coordinated"),
    ]
    # Roster CT starts normally: neither side receives free turns or buffs.
    content.missions[MISSION] = courtyard
    content.validate(rules=tactical_rpg_rules())
    return content


def encounter_preview(content=None):
    content = content or jeanne_siege_content()
    rules = tactical_rpg_rules()
    battle = Battle(content, MISSION, seed=1, rules=rules)
    return {
        "mission": MISSION,
        "objective": battle.mission.objective,
        "board": [battle.board.width, battle.board.height],
        "player": [u.id for u in battle.units if u.team == "player"],
        "defenders": [{"id": u.id,
                       "role": next((t for t in u.tags if t.startswith("squad:")), "none"),
                       "weapon": u.weapon, "pos": list(u.pos)}
                      for u in battle.units if u.team == "enemy"],
        "threats": tactical_intents(battle),
        "replay_verified": (Battle.replay(battle.recording(), rules=rules).digest()
                            == battle.digest()),
    }


def balance_comparison(*, seeds=SEEDS, max_commands=300):
    coordinated = jeanne_siege_content(coordinated=True)
    isolated = jeanne_siege_content(coordinated=False)
    return compare_compositions(
        {"coordinated": coordinated, "isolated": isolated}, MISSION,
        baseline="isolated", seeds=seeds, max_commands=max_commands,
        rules=tactical_rpg_rules())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preview", action="store_true",
                       help="Print positions, roles and current known threats")
    group.add_argument("--export", type=Path, metavar="FILE",
                       help="Export editable Content JSON for the Studio")
    group.add_argument("--compare", action="store_true",
                       help="Compare matched seeds, with and without squad roles")
    parser.add_argument("--max-commands", type=int, default=300)
    args = parser.parse_args(argv)
    if args.export:
        args.export.write_text(
            json.dumps(jeanne_siege_content().to_dict(), ensure_ascii=False, indent=2)
            + "\n", encoding="utf-8")
        print(str(args.export))
    elif args.compare:
        print(json.dumps(balance_comparison(max_commands=args.max_commands),
                         ensure_ascii=False, indent=2))
    else:
        print(json.dumps(encounter_preview(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
