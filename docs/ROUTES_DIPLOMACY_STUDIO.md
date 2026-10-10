# 2.5.4.4 — Routes & Diplomacy Studio

A siege is authored in **Studio → Campagne & siège → Itinéraires & diplomatie**.
This panel is a visual editor for the existing `SiegeCampaign` and
`CampaignRoutesPolicy` contracts. It does not create new combat outcomes.

## Authoring workflow

1. In **Fronts et finale**, create at least two distinct fronts. Choose the
   final sector and tactical prerequisites with accepted outcomes.
2. In **Logistique & convois**, configure finite strategic provisions. Route
   costs and diplomatic payments cannot be played without them.
3. In **Itinéraires & diplomatie**, choose **Activer itinéraires**. This creates
   the free `breach` route (same prerequisites as the current finale) and a
   costly `direct` route. A direct route cannot be free of both resource and
   troop costs.
4. To author infiltration, name a route (e.g. `tunnels`), select the real
   front `tunnels`, enter accepted tactical results (e.g. `victory`), then
   set provisions and troop losses and **Enregistrer itinéraire**. The
   `tunnels` sector must be won in a **real** tactical battle; advancing the
   strategic clock cannot synthesize that victory.
5. In **Issues tactiques**, author the consequence of a *partial victory*
   (requires a real interact/defense sabotage event), a *negotiation* (spends
   real provisions), or a *withdrawal*. Losses on another front are applied
   by the existing engine, not by the visual editor.
6. In **Traités**, select a negotiated front, a different front containing
   the actual proof object, the proof event, and optional enemy IDs that will
   stand down in the final battle. All IDs are checked; the final cannot be
   emptied of enemies.
7. In **Reconquête / riposte**, provide a separate tactical recovery
   mission, finite cost and recovered strength. Optionally configure an
   enemy counteroffensive with its turn, a playable tactical mission and
   army-pressure parameters.
8. Click **Prévisualiser conditions**, save the `.game.json` project and
   start a new playable siege from the Player menu. Replay/checkpoint
   identities include all policy changes.

## Player commands

The normal Player **Timeline / Fronts** screen now displays the final gate
and current route status. Choose an alternative via **Engager itinéraire**:
it commits once, charging actual provisions and casualties.

On eligible focused fronts, **Négocier le passage**, **Valider objectif
partiel**, and **Ordre de retraite** execute the same validated campaign
choices as the command center. Once a covered front is lost, select it and
choose **Reconquérir ce secteur**. Recovery uses a real separate `Battle`,
reuses the standard Player combat panel, and its commands, outcome and
autosave pass through `MultiFrontSession.execute_recovery`. Unfinished
recovery blocks incompatible strategic commands; it may be explicitly
abandoned.

No route choice or diplomatic flag directly grants tactical victory.
The final encounter must still resolve in the tactical engine.

## Backward compatibility and validation

The `routes`, `treaties`, `recovery` and `counteroffensives` policy fields
are optional. Existing projects without these fields preserve their schema
and sessions. When present, they are checked by `CampaignRoutesPolicy`
during `GameProject.validate`, then by the real `MultiFrontSession`
constructor when an editor mutation is committed. Invalid or contradictory
definitions are rejected without mutating the existing project.

Old saved game sessions remain readable when the project/content are
unchanged. As before, changing an authored campaign policy invalidates
checkpoints tied to its old project checksum.

### Acceptance tests

```bash
python -m unittest tests_standalone.test_routes_diplomacy_studio -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_routes_diplomacy_gui.py -v
```

Next steps: richer tactical side-mission presentation for convoy rescue,
scene/voice consequences of treaties, and a draggable route graph.
