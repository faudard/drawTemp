"""Playable siege mission fixtures: python -m examples.siege_scenarios."""
import json
from sporebound.model import Content

def siege_content():
    def unit(uid, team, pos):
        return {"id": uid, "name": uid.replace("_", " ").title(), "team": team, "pos": pos}
    def mission(mid, title, objects, triggers, goal):
        return {
            "id": mid, "name": title, "board": {"width": 12, "height": 8},
            "units": [unit("captain", "player", [1, 3]), unit("engineer", "player", [1, 5]),
                      unit("defender", "enemy", [9, 3])],
            "objective": "reach", "goal": [goal],
            "objects": objects, "triggers": triggers
        }
    gate = {"id": "main_gate", "kind": "door", "pos": [8, 3], "open": False, "hp": 4}
    ram = {"id": "ram", "kind": "ram", "pos": [3, 3], "link": "main_gate", "power": 1}
    catapult = {"id": "catapult", "kind": "catapult", "pos": [2, 5], "link": "main_gate",
                "power": 2, "range": 10}
    troll = {**unit("siege_troll", "enemy", [4, 1]), "kind": "monster",
             "footprint": [2, 2], "max_hp": 150, "hp": 150, "move": 2,
             "attack": 16, "weapon_power": 12}
    return Content.from_dict({
        "version": 1, "skills": [],
        "missions": [
            {**mission("castle_troll", "Stop the siege troll", [gate.copy()], [], [10, 3]),
             "units": [unit("captain", "player", [1, 3]), unit("engineer", "player", [1, 5]), troll]},
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
    })

if __name__ == "__main__":
    data = siege_content()
    print(json.dumps({"missions": list(data.missions)}, indent=2))
