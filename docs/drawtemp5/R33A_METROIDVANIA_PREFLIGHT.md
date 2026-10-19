# R33.A — Metroidvania ability gates and reachability preflight

**Status:** first R33 (7.3) headless slice in the integration branch. **Not** a
Platformer/Metroidvania feature release or an R33 exit gate.

## Canonical ownership and compatibility

- The opt-in world graph is `GameProject.extensions["drawtemp.metroidvania"]`
  with the existing R24 extension envelope: `{"schema_version": 1, "data": ...}`.
  There is no sidecar file, new save format or separate scene database.
- Each room ID must reference an existing `GameProject.exploration` scene;
  the scene remains owned and validated by the canonical Project/Content pair.
- `GameProject.validate` validates this namespace when present and refuses
  invalid, future-versioned, dangling and unbounded graph definitions.
- Old projects have no new field and retain the same serialization, CT behavior
  and replay. The extension is inert to `GameSession` for now.

## Declarative v1 fields

```json
{
  "version": 1,
  "rooms": ["village", "ruins", "citadel"],
  "start": "village",
  "goal": "citadel",
  "starting_capabilities": [],
  "pickups": [
    {"id": "boots", "room": "ruins", "grants": ["double_jump"]}
  ],
  "links": [
    {"id": "visit", "source": "village", "destination": "ruins", "requires": []},
    {"id": "return", "source": "ruins", "destination": "village", "requires": []},
    {"id": "boss_gate", "source": "village", "destination": "citadel",
     "requires": ["double_jump"]}
  ]
}
```

This is a **sample payload**; the listed room IDs must actually exist in the
project's exploration catalogue before the extension is saved.

The public functions are `validate_metroidvania(raw, scene_ids=...)` and
`analyze_metroidvania(raw, scene_ids=..., state_budget=20000)`.
All directed edges are explicit, including returns. Abilities can be granted
on entering a room and are monotonic (never consumed in v1). Every gate is
an AND of capability IDs. Unrecognized fields, duplicate IDs, nonexistent
room refs and undefined gate capabilities are errors.

## Static analyzer

The bounded BFS explores `(room, unlocked_ability_bitset)`, gives a
deterministic route witness to the goal, identifies rooms with no reachable
state, and reverse-searches to find **reachable softlocks** (states that can
no longer lead to the goal). All outcomes carry `complete` and `safe`;
state budget overflow is always **inconclusive / not safe**, never falsely
green. Limits: 128 rooms, 512 links, 32 pickups, 12 distinct abilities,
maximum 50,000 visited states. Softlock examples are capped at 100.

`safe=true` proves only this **abstract** monotonic progression model:
it does **not** prove jumps can cross real geometry, player movement,
physics/colliders R32, boss victory, enemy respawn, checkpoints, camera
transitions, actual Player wiring, exports or UX.

## Test command

```bash
python -m unittest discover -s tests_standalone -p 'test_r33_metroidvania.py' -v
```

The tests exercise double-jump gating, directed softlocks, circular locked
progression, deterministic witnesses, strict schema/refs, fail-closed search
budgets and isolation from legacy GameProject data.

## Remaining R33 gates

R33.1–R33.2: platformer profile, side-view rendering and room editor;
R33.4–R33.10: runtime mobility, rewards, checkpoints, combat, exploration
and optional camera UX; R33.12: a real three-room, two-capability, boss
Studio→Player→save/load→export tutorial. These depend on the **actual** R31
and R32 implementations; their absence must keep the R33 release NO-GO.
