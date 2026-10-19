"""R26 headless smoke: a deterministic action input trace, no Qt dependency."""
import json

from sporebound.action_runtime import ActionRuntime


def main():
    scene = {
        "id": "r26_meadow", "width": 7, "height": 7,
        "walls": [[5, 5]], "hero": {"pos": [1, 1], "hp": 8},
        "enemies": [{"id": "wolf", "pos": [3, 1], "hp": 2,
                     "patrol": [[3, 1], [3, 2]]}],
        "objects": [{"id": "chest", "kind": "chest", "pos": [1, 2],
                     "item": "key", "requires": ""},
                    {"id": "gate", "kind": "door", "pos": [2, 1],
                     "item": "", "requires": "key"}],
    }
    game = ActionRuntime(scene)
    actions = [{"interact": "chest"}, {"interact": "gate"},
               {"dx": 1, "attack": True}] + [{}] * 12 + [{"attack": True}]
    for n, action in enumerate(actions, 1):
        game.step({"tick": n, **action})
    verified = ActionRuntime.from_recording(game.recording(), expected_scene=scene)
    assert verified.digest() == game.digest()
    print(json.dumps({"tick_hz": 60, "scene": scene["id"],
                      "state_digest": game.digest(),
                      "hero": game.snapshot()["hero"],
                      "inventory": game.inventory, "flags": game.flags},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
