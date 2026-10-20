# R61.A — Village simulation (headless, opt-in)

Status: **implementation PR**, not an R61 release gate. R61.B visual City Planner
and R61.C playable village have not been certified. The roadmap dependencies
R35 / R45 / R55 / R56 / R60 must be independently validated on `master`.

## Canonical model

- **GameProject.extensions[`org.drawtemp.systems`]**: R55 resources, producer
  recipes and capacity. It is the *only* authoritative stock definition.
- **GameProject.extensions[`org.drawtemp.settlement`]**: version 1 declarative
  zones, buildings, residents and consumption contracts. No arbitrary scripts.
- **GameSession._systems**: single R55 fixed-tick economy, operation receipts
  and stock journal. A settlement projection gates producers by workforce and
  consumes stocks in stable resource-name order after production.
- No extra tick, sidecar JSON, stock duplication, Qt coupling or CT mutation.
- Projects without the R61 extension use byte-compatible R55 checkpoint shapes.

## Small project extension example

Both extensions are project-owned envelopes with
`{"schema_version": 1, "data": ..., "references": []}`.

```json
{
  "org.drawtemp.systems": {
    "schema_version": 1,
    "references": [],
    "data": {
      "version": 1,
      "resources": [
        {"id": "grain", "initial": 10, "capacity": 50},
        {"id": "food", "initial": 1, "capacity": 50},
        {"id": "wood", "initial": 8, "capacity": 50},
        {"id": "plank", "initial": 0, "capacity": 50}
      ],
      "producers": [
        {"id": "farm", "inputs": {"grain": 1},
         "outputs": {"food": 2}, "interval": 2},
        {"id": "sawmill", "inputs": {"wood": 1},
         "outputs": {"plank": 1}, "interval": 1}
      ],
      "merchants": [],
      "quests": []
    }
  },
  "org.drawtemp.settlement": {
    "schema_version": 1,
    "references": [],
    "data": {
      "version": 1,
      "zones": [{"id": "village", "scene": "arrival", "capacity": 2}],
      "buildings": [
        {"id": "mill", "zone": "village", "producer": "farm",
         "workers": 1, "cost": {}, "built": true},
        {"id": "workshop", "zone": "village", "producer": "sawmill",
         "workers": 1, "cost": {"wood": 2}, "built": false}
      ],
      "residents": [{"id": "ada"}, {"id": "bob"}],
      "needs": [{"resource": "food", "quantity": 1, "interval": 1}]
    }
  }
}
```

The zone `scene` must exist in the GameProject's exploration scenes
(or in the underlying mission IDs). One and only one building must reference
each R55 producer. A built building consumes a zone slot; an assigned worker
counts towards its required staffing. Production stops automatically if a
building is absent or understaffed.

## Headless scenario

After loading a project with the extensions above, the GameSession API is:

```python
session.system_advance(3)  # food runs out; shortage counter increases
assert session.settlement_state()["shortages"]["food"] == 2
session.settlement_assign("ada", "mill", "hire-001")
session.system_advance(1)  # the farm produces food; the shortage clears
session.settlement_build("workshop", "build-001")  # spend 2 wood
session.settlement_assign("bob", "workshop", "hire-002")
session.system_advance(2)
snapshot = session.recording()  # standard GameSession save/replay contract
```

Builds and staffing commands require unique receipt IDs. Repeating the same
receipt with the same parameters is idempotent; reusing the receipt for a
different operation is rejected. Underflow, overflow, saturated zones, excess
staffing, invalid resource dependencies, and unsupported schema versions fail
closed. A settlement checkpoint is verified by replaying the existing R55
operation journal, even when the outer GameSession digest is recomputed.

## Verification

```sh
python -m unittest tests_standalone.test_r61_settlement -v
python -m unittest tests_standalone.test_r55_system_design -v
python -m unittest tests_standalone.test_r35_living_world -v
```

**Gate matrix to complete before declaring R61:** headless Windows/macOS/Linux,
real Studio→Player authoring, visual zone placement, Undo/Redo, a multi-day
colony simulation with failure/intervention/recovery, load/save parity, input
and accessibility review, performance profiling and R56/R60 dependency closure.
Unit tests are not evidence of those gates.
