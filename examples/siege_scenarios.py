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
    ram = {"id": "ram", "kind": "ram", "pos": [3, 3], "link": "main_gate", "power": 1}
    catapult = {"id": "catapult", "kind": "catapult", "pos": [2, 5], "link": "main_gate",
                "power": 2, "range": 10}
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
    throne['triggers'] = [{"id": "last_stand", "condition": "tick", "value": 0,
                           "actions": [{"kind": "message", "text": "The royal guard defends the throne. Defeat every defender!"}]}]
    data['missions'].extend([ramparts, courtyard, throne])
    return Content.from_dict(data)

if __name__ == "__main__":
    data = siege_content()
    print(json.dumps(data.to_dict(), indent=2))
