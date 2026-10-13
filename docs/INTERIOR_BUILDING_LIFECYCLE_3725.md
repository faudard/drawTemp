# 3.7.25 — Interior Builder: safe authored-floor lifecycle

This increment finishes a dangerous authoring edge rather than changing
vertical combat rules. All missions continue using Content v1.

## What moves with an authored building?

Moving a persistent Maison, Tour or Ruines with authored upper decks now
relocates **in the same validated transaction**:

- The building's visual/tactical ground footprint and retained identity;
- All its interior decks (tiles stay local to the stable building identity);
- Upper-floor actors standing within its original footprint;
- Stair endpoints attached to its interior, including the corresponding N0
  landing inside the original building footprint.

The result is checked by the existing `Content.from_dict` validator. If a
connector would point outside a valid floor, or a new location intersects
another building, no edit is committed. A `Document.replace` operation can
be undone/redone as one action.

Ground actors, objectives and independent external passages do **not** follow
the building: the conventional tactical board remains authoritative. A
translation that would intersect a ground actor is refused.

## Explicitly not supported yet

- Changing rotation, door arrangement or type while decks are authored: this
  needs a future remapping policy for local coordinates, stair links and actors,
  so the editor now rejects it with an actionable error.
- Group translation/duplication of buildings that carry floors: also refused
  until connectors can be remapped consistently.
- Deleting an interior floor/building while actors or stair endpoints still
  occupy its interior: first move occupants to another valid level, remove the
  connectors, then delete.
- Duplicating a building still duplicates only the building shell, not its
  decks/links/actors. Author new decks explicitly on the duplicate.

No new 3D LOS, height-based floor inference, AoE or falling is introduced.

## Reproducible gates

```sh
python -m unittest tests_standalone.test_interior_building_lifecycle_3725 -v
python -m unittest tests_standalone.test_tactical_levels_3720c -v
python -m unittest tests_standalone.test_interior_builder_3720_gate -v
```

Required outcomes: move the house with enemy upstairs; verify its stair
endpoints relocate and its authored deck remains intact; move to the stair,
climb, attack, save/reload, and compare replay digests. An invalid rotation,
deletion or group move leaves the original content untouched.
