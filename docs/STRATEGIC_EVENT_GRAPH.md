# 2.5.4.5 — Strategic Event Graph

Create siege-wide causal events visually in **Studio → Campagne & siège →
Graphe stratégique**. A graph is optional in a saved `GameProject.sieges[]`
blueprint. If omitted, historical project files, engine digests and replay
versions remain unchanged.

## Visual workflow

1. Create a siege and its fronts as usual. Select **Graphe stratégique**
   and add an event with **Nouveau**. Every event has a unique ID, one
   condition tree and one or more consequences.
2. Build the condition with typed presets:
   - **Tour global ≥ N** (`turn_at_least`) — a real global strategic turn.
   - **Statut d'un front** (`front_status`) — a verified strategic result;
     never a forecast from the Studio.
   - **Événement tactique** (`battle_event`) — an actual interaction, gate
     breach, defense sabotage, passage installation or battle result in the
     chosen front. The tactical object ID is validated against the mission.
   - **Événement de la timeline** (`timeline_event`) — a recorded strategic
     event from the existing engine, such as a convoy arrival.
   - **Après un événement** (`fired`) — another event node's recorded firing,
     for serial causality. Unknown names and cycles are rejected.
3. Use **Envelopper** to make ET, OU or NON groups. Select a group and
   **+ Dans ET/OU** to append operands; replace or delete branches via their
   paths. Conditions are bounded in size and nesting. NOT can negate status
   and event predicates, but not another event's `fired` state (to avoid
   contradictory evaluation-order semantics).
4. Edit the event's consequence list: disable reinforcement waves, open a
   genuine mission door, disable a genuine defensive object, reduce the
   strength/opposition of a non-final front, change a live front doctrine, or
   emit a short `strategic_signal` visible in the strategic timeline.
5. **Simuler 8 tours** displays a read-only strategic projection. It
   advances the same strategic mechanics as the runtime but **does not**
   manufacture tactical interactions or boss victories. Save the project
   to persist your graph.

## Execution and security

The real `MultiFrontSession` checks the graph at journaled tactical command
boundaries (`execute`) and strategic synchronizations (`advance`). Every
node is applied at most once per session. A stable topological ordering allows
node A to trigger B in the same evaluation, while cycles are invalid.

All condition data is strictly typed and no user Python code is evaluated.
Tactical-event predicates inspect actual `Battle.events` only; AI forecasts
or previewed operations cannot satisfy them.

Strategic effects reuse the project's validated front mechanics. A direct
strategic attrition action **cannot target the final boss front**, ensuring
the final battle requires a real tactical outcome. Events referring to a front
must be deleted or edited before that front is removed.

The graph and its fired IDs enter the session checksum. Graph-enabled
recordings use **multi_front version 6**; legacy recordings continue on
the original versions and are not silently converted. Checkpoint replay
verifies the original graph against the Studio/Player project; modifying
the graph intentionally invalidates old sessions tied to that blueprint.

## Test gates

```shell
python -m unittest tests_standalone.test_strategic_event_graph -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_strategic_event_graph_gui.py -v
```

The GUI is an event authoring interface; it does not yet directly connect
`strategic_signal` events to narrative voice/cinematic playback. That bridge
is a future Content/Story/Cinematic Studio integration.
