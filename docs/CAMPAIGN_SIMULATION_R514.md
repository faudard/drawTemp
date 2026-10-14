# R5.14 — Campaign Simulation Studio

The **Campaign Simulation** Studio tab provides a safe way to explore candidate
story/mission paths and compare consequences without modifying an active
Campaign slot, GameSession checkpoint, project, or Studio authoring history.

## Using the simulator

1. Select a campaign in **Jeu, campagnes et sauvegardes**.
2. Open **Campaign Simulation**, then choose **Nouvelle simulation** or
   **Depuis partie chargée (copie)**. The second option copies a currently
   loaded compatible campaign; no save is opened for writing.
3. Pick an offered narrative choice or a hypothetical mission result and
   press **Exécuter l'action** (double-click also works). The action tree grows
   with one snapshot node per accepted action.
4. Click an earlier tree node or use **Revenir au parent** to go back to a
   decision. Select another choice/result to create a diverging path.
   **Créer une bifurcation** creates an explicit alternate checkpoint.
5. Use **Comparer A** and **Comparer B** at two selected states, then inspect
   the **Différences A / B** tab. The report includes each route's actions,
   nearest shared ancestor, differing fields, resources, flags, wounds,
   mission availability and reached endings.
6. The **État persistant** tab shows the exact snapshot of the selected node;
   **Couverture explorée** lists endings and missions *observed in this tree*.
   This is not exhaustive campaign QA.
7. If Content, GameProject or the selected campaign changes, the sandbox is
   invalidated. Start again rather than replaying speculative outcomes against
   changed data. Use the existing R5.11 QA for static bounded route checks.

## What is actually simulated

- **Narrative choices** call the exact `StoryBook.choices/choose` APIs.
  Existing conditions, scene chaining, flags and choice effects are evaluated
  by the runtime implementation.
- **Mission gates** use the same `available_missions` condition logic as
  GameSession and PlayerSession. They cannot be bypassed in the simulator.
- **Hypothetical victory** completes the selected mission, applies its known
  fixed authored reward, unlocks `Mission.next_missions` or opens an
  `after_mission` story scene, and calls the canonical `campaign_flow.settle`.
- **Hypothetical defeat** does not complete the mission and applies any
  declared defeat consequences through `campaign_flow.settle`.
- **No tactical Battle is executed.** There is **no proof** of victory,
  AI decisions, battle event triggers, XP, tactical loot, offscreen front
  settlement, world travel/location enforcement or replay determinism.
  Hypothetical mission rewards are only fixed authoring values; final gameplay
  balance must still be validated with actual GameSession/Battle playthroughs.

A normal GameSession recording can NEVER be manufactured from these symbolic
branches. The `SimulationNode.verified_battle` field is always false.

## Design and safety guarantees

- `CampaignSimulation` lives in a Tk-free module with immutable-in-practice
  node history. The public snapshot/inspection APIs return deep copies,
  never the owned branch state.
- Invalid choices, locked missions, invalid node IDs, stale save definitions,
  node budgets, or depth budgets fail without publishing a node or moving the
  selected cursor. The default limits are **512 nodes / 96 levels**, with
  configurable bounded maxima.
- The simulator holds **no path** to a real save, provides no write action,
  and never calls `Campaign.save`, `GameSession.save`, `SessionStore.save`,
  `GameProject.save`, or a Studio transaction write.
- A loaded progress snapshot is checked against the existing campaign flow
  fingerprint and story definition. Noncompatible saves are rejected rather
  than migrated silently.
- Refreshes invalidate transient trees whenever the active project's
  content, campaign or settings change, including Undo/Redo.
- No new `Content`, `GameProject`, `Campaign` or `GameSession` save
  schema is added.

## Validation

```bash
python -m unittest tests_standalone.test_campaign_flow_simulation_r514 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
  tests_standalone.test_campaign_flow_simulation_r514_gui -v
```

Both commands are explicitly added to the existing standalone CI workflow.
Use R5.11's route QA and R5.12's exported-player replay gate as separate
certification evidence.

**Stacked PR order**: #162 (Campaign Flow) → #177 (Visual Campaign Authoring)
→ R5.14 (Simulation Studio). Rebase/retarget in that order after merges.
