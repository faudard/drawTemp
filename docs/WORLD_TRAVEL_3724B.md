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
- The campaign mission list remains available for legacy projects and
  missions omitted from a partial map. Authored world destinations instead
  direct the party to the World screen before they can be entered.

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

## 3.7.24C — Pathfinder-inspired events on canonical roads

Add an optional `events` list to the existing `world` manifest.
Each entry binds an existing road (two linked Mission IDs) to an existing
`story.scenes` scene, with an optional StoryBook `when` condition.
Only one authored encounter may occupy the same road. Events fire exactly
once per campaign, halfway through the route in **either direction**.

```json
{
  "id": "caravane",
  "from": "garden",
  "to": "escape",
  "scene": "road_caravane",
  "when": {"completed_mission": "garden"}
}
```

The normal StoryBook choice UI takes over the Player; the party remains
positioned halfway along the route. The selected choice can apply any
existing validated narrative effects (gold, flags, unlocks, equipment, etc).
Once the choice resolves, travel resumes from its saved position. Mid-event
saves and recovery use the usual verified GameSession snapshot.

- `world_evt_<id>` is the only new once-only flag; no bespoke event log
  or dialogue/replay schema is introduced.
- Event specifications are gameplay content in the checkpoint fingerprint,
  while purely decorative world coordinates remain excluded.
- Projects without world events retain their pre-existing digest and saves.
- Use `python -m examples.world_route_events_3724c --output /tmp/roads.json`
  to generate a playable, choice-driven world journey with tactical consequences.
- Gate: `python -m unittest tests_standalone.test_world_events_3724c -v`.

Deferred: random event tables, encounter combat on routes, cooldowns/repeatable
events, branching physical roads and a dedicated event inspector in Studio.
