# 3.7.24B — Continuous World Journey (first playable slice)

The 3.7.24A World Map (#109) already renders the canonical mission graph.
This follow-up adds a **real, persistent party cursor** traveling between
accessible locations. It deliberately does **not** add a new mission graph.

## Player contract

- Open **Carte du monde** from the campaign (no pending narrative dialogue).
- Click a reachable unlocked/completed destination. The party travels along
  the existing `Mission.next_missions` connections, including reverse trips.
- Movement is interpolated across each map edge; every step is checkpointed
  via the existing `PlayerController._apply` / `SessionStore`. Reopening a
  save mid-route restores the party's current interpolated position and goal.
- Click a mission **at the party's location**, with no journey in progress,
  to enter its normal cinematic, deployment and battle. Locked/completed nodes
  cannot launch a mission. Clicks on unrelated/locked nodes do not unlock them.
- The campaign mission list is preserved for legacy projects and for missions
  omitted from a partial map.

## Data ownership and compatibility

`sporebound/world_travel.py` is headless. It derives the traversable roads
from the canonical campaign graph, filtering nodes against the saved
`Campaign.unlocked` and `Campaign.completed`. Four bounded story flags
(`world_walk_at`, `world_walk_goal`, `world_walk_via`,
`world_walk_step`) use the existing Campaign v1 save contract. They are
absent until first travel. No `tile.height`, battle coordinates, new
`.game.json` fields, schema migration or world-specific save file is used.

All reloaded journey states are validated, including route adjacency, allowed
missions and step range. The same map can be edited in Studio; world pin
positions remain cosmetic and excluded from the project fingerprint.

## Gates

```sh
python -m unittest tests_standalone.test_world_travel_3724b -v
python -m unittest tests_standalone.test_world_map_3724a -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_world_map_3724a_gui -v
```

## Remaining for continuous exploration 3.7.24C+

This slice is continuous **along authored world routes**, not unrestricted
free movement across a landscape. Off-road travel, authored waypoints,
contextual encounters, seamless entrance into existing exploration stages,
camera zoom/pan and geography-based region transitions remain to be designed
against the existing `Exploration` and `GameSession` contracts.
