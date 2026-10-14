# R5.13 — Visual Campaign Authoring

R5.13 adds a **Campaign Flow 3.0** Studio tab for authoring the existing
`GameProject.campaign_flow` optional sidecar without typing JSON. The same
`Campaign`, `narrative.matches`, `Campaign.prepare`,
`GameSession` and `PlayerSession` contracts remain canonical.

## Workflow

1. Open **Campaign Flow 3.0** in the Studio.
2. Select **gate** and an existing mission (e.g. `hold`). Compose its
   conditional entry rule with a typed predicate: Flag =, Flag ≥, Flag ≤,
   Mission terminée or Or ≥.
3. Replace/init the root, wrap it in ET / OU / NON, add predicates under a
   group, or delete a node. The tree shows the exact nesting. An absent
   gate means the mission is not additionally restricted.
4. Switch to **ending**, enter a safe identifier, and author the ending
   condition in the same tree. Clearing its root deletes the ending.
5. Pick a mission and an outcome (`victory` or `defeat`). Add, replace,
   remove and reorder *typed* consequences with two ordinary fields. The
   editor supports `set_flag`, `add_flag`, `gold`, `grant_item`,
   `unlock_mission`, `recruit_hero`, `equip_hero`, `wound` and
   `heal_wound`.
6. Use **Tester sur la campagne** for read-only condition evaluation and
   **Analyser parcours** for bounded QA. Preview is not a tactical replay
   or a guarantee of reaching every ending.
7. Use the Studio's global **Annuler / Rétablir** or **Enregistrer projet de
   jeu…**. All authoring edits are fully validated before assignment; an
   invalid command changes neither the live project nor the history.

All edits pass through `campaign_flow_authoring.py` (pure model commands)
then `GameProject.from_dict`, which validates every mission reference,
predicate, consequence and ending. No Tk controls are imported into the
runtime model. The Studio owns the sole transactional history for Content
and GameProject; no local competing command stack or alternate save file.

## Mission consequences and runtime

Effects are applied **in their authored order** when a genuine victory or
defeat is settled by the runtime. The previous R5.B ledger prevents a
duplicate payout on repeated settlement, including after checkpoint replay.
The UI does not run effects as a preview, avoiding fake campaign rewards.

The mission gating is evaluated at the actual GameSession/PlayerSession
mission-entry boundary and at the Studio launch button. Creating an
`ending` declaration merely exposes a condition to the state inspector;
it does not automatically end combat, switch scenes or choose a narrative
path. Existing StoryBook scene links remain responsible for story choices.

## Verification

```bash
python -m unittest tests_standalone.test_campaign_flow_authoring_r513 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
  tests_standalone.test_campaign_flow_authoring_r513_gui -v
```

Gates: nested ET/OU/NON editing; invalid reference rejection; lossless
save/load; typed effects; effect order and atomicity; GameSession parity;
global undo/redo; real Tk surface. Both gates are explicit steps in the
existing `Standalone gameplay` workflow.

### Stacking

This PR is based on `feat/r5b-campaign-flow-3-0` (#162), which must be
merged first, or R5.13 must be rebased onto `master` after that merge.
The R5.B data model, save identity, QA and export gates are prerequisites.
