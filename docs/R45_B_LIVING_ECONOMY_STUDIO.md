# R45.B — Living Economy Studio Qt (incremental)

Status: **implemented in a stacked PR on R45.A; not certified**.

## Entry point and scope

Studio Qt Widgets > **Outils** > **Économie vivante : commerces et recettes R45**.

- Merchant catalogue: NPC, authored activity and scene, faction, reputation
  threshold, item identities, integer buy/sell prices, daily stock.
- Crafting: identical authority fields, inputs/outputs with typed item
  selectors and bounded quantities, gold cost and production-per-day cap.
- The NPC calendar remains authored by R35's **Monde vivant** dialog. The
  economy editor reads those schedule identities, without cloning schedules.
- Read-only preview resolves R35 schedule projection and prints source
  catalogue, reputations, stock and recipe limits; empty story flags are
  explicitly indicated. Player inventory and time never advance in preview.

## One source of truth

`EconomyDraft` snapshots one version of the project's
`org.drawtemp.livingworld` extension, edits only its optional `shops` and
`recipes` keys, and uses the existing `preview_living_world` /
`AuthoringSession.apply` pipeline. A successful Apply creates one undo/redo
transaction across shops and recipes; Cancel never edits the canonical pair.
The draft pins the initial session revision: concurrent modifications,
including edit→undo ABA, reject stale Apply.

No changes to CT, game replay, Campaign inventory or runtime ledger are made
by UI operations. Existing R35 player/clock contracts remain authoritative.

## Current limitations / future gates

- The first R45.B editor covers commerce and crafting, not independent
  simulation of NPC production or farming. Missing NPCs/factions/activities
  must be authored in the existing living-world document.
- Offscreen GUI smoke and pure authoring tests are **not** onscreen UX or
  GPU certification. Verify keyboard tab-order, varying DPI and author workflow
  on actual Windows, Linux and macOS hardware before closing R45.B.
- R45.C requires a playable 7-day village slice, Player exchange UX, timed
  quests, saves, export evidence and independent user playtesting.

## Tests

```bash
python -m unittest tests_standalone.test_r45_economy_authoring \
  tests_standalone.test_r45_crafting \
  tests_standalone.test_r35_commerce -v
QT_QPA_PLATFORM=offscreen python -m unittest \
  tests_standalone.test_r45_economy_qt -v
```
