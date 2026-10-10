"""Playable siege mission fixtures: python -m examples.siege_scenarios."""
import json
from sporebound.model import Content

def siege_content():
    def unit(uid, team, pos):
        return {"id": uid, "name": uid.replace("_", " ").title(), "team": team, "pos": pos}
    def mission(mid, title, objects, triggers, goal):
        return {
            "id": mid, "name": title, "board": {"width": 12, "height": 8,
                      "tiles": [{"pos": [8, y], "blocked": True} for y in range(8) if y != 3]},
            "units": [unit("captain", "player", [1, 3]), unit("engineer", "player", [1, 5]),
                      unit("defender", "enemy", [9, 3])],
            "deployment": [{"id": "assault_camp", "cells": [[x,y] for x in range(3) for y in range(2,7)]}],
            "objective": "extract", "goal": [goal],
            "objects": objects, "triggers": triggers
        }
    gate = {"id": "main_gate", "kind": "door", "pos": [8, 3], "open": False, "hp": 4, "locked": True}
    ram = {"id": "ram", "kind": "ram", "pos": [3, 3], "link": "main_gate", "power": 1,
           "team": "player", "hp": 18, "max_hp": 18, "repair": 8, "repair_charges": 2}
    catapult = {"id": "catapult", "kind": "catapult", "pos": [2, 5], "link": "main_gate",
                "power": 2, "range": 10, "team": "player", "hp": 12, "max_hp": 12,
                "ammo": 3, "repair": 6, "repair_charges": 1}
    troll = {**unit("siege_troll", "enemy", [4, 1]), "kind": "monster",
             "footprint": [2, 2], "max_hp": 150, "hp": 150, "move": 2,
             "attack": 16, "weapon_power": 12}
    data = {
        "version": 1, "skills": [],
        "missions": [
            {**mission("castle_troll", "Stop the siege troll", [gate.copy()], [], [10, 3]),
             "units": [unit("captain", "player", [1, 3]), unit("engineer", "player", [1, 5]), troll],
             "objective": "eliminate"},
            mission("castle_ram", "Break the gate with a ram", [gate.copy(), ram], [
                {"id": "gate_warning", "condition": "tick", "value": 8,
                 "actions": [{"kind": "message", "text": "Archers defend the ramparts!"}]}
            ], [10, 3]),
            mission("castle_artillery", "Bombard the castle gate", [gate.copy(), catapult], [],
                    [10, 3]),
            mission("castle_relief", "Breach the gate before relief arrives",
                    [gate.copy(), ram.copy()], [
                        {"id": "relief", "condition": "tick", "value": 12,
                         "actions": [{"kind": "wave", "actors": [
                             unit("reinforcement_1", "enemy", [10, 5]),
                             unit("reinforcement_2", "enemy", [10, 6])]}]}
                    ], [10, 3])
        ]
    }
    oil = {"id": "boiling_oil", "kind": "defense", "pos": [9, 1], "team": "enemy",
           "cells": [[7, 2], [7, 3], [7, 4]], "power": 18, "charges": 2, "cooldown": 20}
    ramparts = mission("castle_ramparts", "Take the ramparts and raise the portcullis",
                       [gate.copy(), ram.copy(), oil,
                        {"id": "grapple", "kind": "passage", "pos": [7, 1],
                         "destination": [8, 1], "enabled": False, "cost": 2},
                        {"id": "stairs", "kind": "passage", "pos": [10, 1],
                         "destination": [10, 3], "cost": 2},
                        {"id": "portcullis_lever", "kind": "switch", "pos": [10, 1],
                         "link": "main_gate"}], [], [10, 3])
    ramparts['board']['tiles'] = [t for t in ramparts['board']['tiles'] if t['pos'] != [8, 1]]
    ramparts['board']['tiles'] += [{"pos": [x, 1], "height": 4} for x in range(8, 11)]
    ramparts['units'].append(unit("oil_keeper", "enemy", [9, 1]))
    courtyard = mission("castle_courtyard", "Take the inner courtyard", [], [], [10, 3])
    courtyard['board']['tiles'] = [{"pos": [6, y], "blocked": True} for y in (0, 1, 2, 5, 6, 7)]
    courtyard['units'] += [unit("courtyard_guard", "enemy", [7, 4])]
    courtyard['objects'] = [{"id": "stone_drop", "kind": "defense", "pos": [7, 4],
                             "team": "enemy", "cells": [[5, 3], [6, 3], [5, 4], [6, 4]],
                             "power": 12, "charges": 3, "cooldown": 20}]
    courtyard['triggers'] = [{"id": "counterattack", "condition": "enter", "pos": [6, 3],
                              "actions": [{"kind": "queue_wave", "actors": [
                                  unit("reserve_guard", "enemy", [10, 6])]}]}]
    throne = mission("castle_throne", "Final battle in the throne room", [], [], [10, 3])
    throne['objective'] = 'eliminate'
    throne['board']['tiles'] = [{"pos": [x,y], "blocked": True} for x in (5, 8) for y in (1, 6)]
    throne['units'] = [unit("captain", "player", [1, 3]), unit("engineer", "player", [1, 5]),
                       {**unit("castellan", "enemy", [10, 3]), "hp": 65, "max_hp": 65, "attack": 12},
                       unit("royal_guard_left", "enemy", [8, 2]),
                       unit("royal_guard_right", "enemy", [8, 4])]
    # The defenders control two limited-use emplacements. A player may
    # disable either post instead of fighting through its fire lane.
    throne['objects'] = [
        {"id": "throne_arrow_slit", "kind": "defense", "pos": [9, 2],
         "team": "enemy", "cells": [[6, 2], [6, 3], [7, 3]],
         "power": 11, "charges": 3, "cooldown": 18},
        {"id": "throne_brazier", "kind": "defense", "pos": [9, 4],
         "team": "enemy", "cells": [[6, 4], [7, 3], [7, 4]],
         "power": 16, "charges": 2, "cooldown": 24},
    ]
    throne['triggers'] = [
        {"id": "last_stand", "condition": "tick", "value": 0,
         "actions": [{"kind": "message", "text": "The royal guard defends the throne. Defeat every defender!"}]},
        {"id": "castellan_second_phase", "condition": "hp_below",
         "unit": "castellan", "percent": 50,
         "actions": [
             {"kind": "message", "text": "The castellan sounds his last horn: protect the throne!"},
             {"kind": "status", "unit": "castellan", "status": "haste", "duration": 35},
             {"kind": "queue_wave", "actors": [
                 unit("throne_reserve_north", "enemy", [11, 1]),
                 unit("throne_reserve_south", "enemy", [11, 6])]},
         ]},
    ]
    # Optional concurrent front: a small supply raid, independent of the
    # sequential castle campaign. Sabotaging its cache can interdict the
    # castellan's *future* reserve waves in a linked multi-front session.
    supply = mission("castle_supply", "Cut the royal supply and reinforcements",
                     [{"id": "supply_cache", "kind": "chest", "pos": [2, 3],
                       "amount": 25}], [], [10, 3])
    supply["objective"] = "eliminate"
    supply["units"].append(unit("supply_scout", "player", [1, 6]))
    supply["units"].append(unit("supply_outrider", "player", [1, 4]))
    supply["board"]["tiles"] = []
    # Self-contained, bounded rescue skirmish. The wagon is a genuine
    # protected player actor: destroying it ends the battle in defeat.
    # The convoy survivors themselves remain in the strategic cargo manifest
    # until resolution, so the encounter cannot duplicate transferred heroes.
    rescue = mission("castle_convoy_rescue", "Recover the stranded supply cart",
                     [], [], [7, 3])
    rescue["objective"] = "eliminate"
    rescue["protected_id"] = "rescue_wagon"
    rescue["board"] = {"width": 9, "height": 7,
                       "tiles": [{"pos": [4, 0], "blocked": True},
                                 {"pos": [4, 6], "blocked": True},
                                 {"pos": [5, 5], "height": 1}]}
    rescue["deployment"] = []
    rescue["units"] = [
        {**unit("rescue_wagon", "player", [3, 3]),
         "max_hp": 45, "hp": 45, "move": 0, "attack": 0, "weapon_power": 1},
        {**unit("rescue_leader", "player", [1, 3]),
         "speed": 20, "weapon": "ranged", "attack_range": 6,
         "attack": 16, "weapon_power": 10},
        {**unit("rescue_scout", "player", [2, 5]),
         "speed": 12, "attack": 9},
        {**unit("road_bandit", "enemy", [6, 2]),
         "hp": 12, "max_hp": 12, "speed": 8},
        {**unit("road_raider", "enemy", [6, 4]),
         "hp": 12, "max_hp": 12, "speed": 8},
    ]
    pursuit = mission("castle_convoy_pursuit", "Hunt the fleeing raiders",
                      [], [], [7, 3])
    pursuit["objective"] = "eliminate"
    pursuit["board"] = {"width": 9, "height": 7,
                        "tiles": [{"pos": [4, 0], "blocked": True},
                                  {"pos": [4, 6], "blocked": True},
                                  {"pos": [5, 3], "cost": 2}]}
    pursuit["deployment"] = []
    pursuit["units"] = [
        {**unit("pursuit_ranger", "player", [1, 3]),
         "speed": 18, "attack": 15, "weapon": "ranged",
         "weapon_power": 11, "attack_range": 6},
        {**unit("pursuit_vanguard", "player", [2, 5]),
         "speed": 12, "attack": 10},
        {**unit("fleeing_bandit", "enemy", [6, 2]),
         "hp": 11, "max_hp": 11, "speed": 8},
        {**unit("fleeing_raider", "enemy", [6, 4]),
         "hp": 11, "max_hp": 11, "speed": 8},
    ]
    tunnels = mission("castle_tunnels", "Infiltrate the throne by the old sewers",
                      [], [], [7, 3])
    tunnels["objective"] = "eliminate"
    tunnels["deployment"] = []
    tunnels["board"] = {"width": 9, "height": 7,
                        "tiles": [{"pos": [4, 1], "blocked": True},
                                  {"pos": [4, 5], "blocked": True},
                                  {"pos": [5, 1], "height": 1}]}
    tunnels["units"] = [
        {**unit("tunnel_sapper", "player", [1, 3]), "speed": 20,
         "attack": 13, "weapon": "ranged", "attack_range": 6,
         "weapon_power": 10},
        {**unit("tunnel_scout", "player", [2, 5]), "speed": 13, "attack": 9},
        {**unit("sewer_sentry", "enemy", [6, 2]), "speed": 8,
         "hp": 18, "max_hp": 18},
        {**unit("sewer_warden", "enemy", [6, 4]), "speed": 8,
         "hp": 18, "max_hp": 18},
    ]
    recovery = mission("castle_gate_recovery", "Retake the fallen gate",
                       [], [], [7, 3])
    recovery["objective"] = "eliminate"
    recovery["deployment"] = []
    recovery["board"] = {"width": 9, "height": 7,
                         "tiles": [{"pos": [4, 0], "blocked": True},
                                   {"pos": [4, 6], "blocked": True}]}
    recovery["units"] = [
        {**unit("relief_captain", "player", [1, 3]),
         "speed": 20, "attack": 15, "weapon": "ranged",
         "attack_range": 6, "weapon_power": 11},
        {**unit("relief_guard", "player", [2, 5]), "speed": 12,
         "attack": 10},
        {**unit("occupying_sergeant", "enemy", [6, 2]), "speed": 8,
         "hp": 18, "max_hp": 18},
        {**unit("occupying_soldier", "enemy", [6, 4]), "speed": 8,
         "hp": 18, "max_hp": 18},
    ]
    data['missions'].extend([ramparts, courtyard, throne, supply, rescue,
                             pursuit, tunnels, recovery])
    return Content.from_dict(data)

if __name__ == "__main__":
    data = siege_content()
    print(json.dumps(data.to_dict(), indent=2))

