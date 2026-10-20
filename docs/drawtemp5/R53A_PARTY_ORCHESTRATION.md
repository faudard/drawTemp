# R53.A1–A2 — Party & Combat Orchestration (runtime candidate)

Roadmap: [R53 in R51–R80](../DRAWTEMP_10_0_TO_12_0_DETAILED_ROADMAP_R51_R80.md).

**Status: CODE IN STACKED PR, NOT R53 CERTIFIED.**
Base: [R41 Party & Encounter PR #381](https://github.com/faudard/drawTemp/pull/381), still pending merge into `master`. Merge R41 first, then retarget/rebase this PR onto `master`.

## One canonical state, opt-in version

- Add an optional `orchestration` node to existing `GameProject.extensions["drawtemp.partyrpg"]["data"]`. Projects without it, including existing R41 and legacy save files, serialize unchanged.
- R41 `ClassicParty` still owns recruitment and the active team. `GameSession` owns orchestration and persistence. `Campaign.heroes` still owns progression/equipment and `Campaign.inventory` owns items. CT `Battle` and R41 RPG remain unmodified.
- R53 leader, slot formation and R41 activations create a bounded 512-entry journal. Replay compares every R53 `active` event against R41's `activate` events even if the outer SHA-256 is recomputed.
- Cooperative combo declarations carry stable member IDs and mode capabilities. Without native skills they remain advisory. **R53.A2 adds an opt-in RPG_TURN executable form**, with exactly one canonical Content damage skill per participating hero. The R41 skill resolver applies every effect, consumes each hero's MP, and skips supporting heroes' next activation. No synthetic damage formulas, new resource wallet, arbitrary scripts, or CT/action executor.
- `freeze_on_encounter` is the only supported authoring policy in v1. Leader/formation changes are rejected during CT/RPG/multifront or pending dialogue. It does not install a new scheduler or override R25 fixed realtime ticks.

Example inside the existing R41 `data` object:

```json
{
  "orchestration": {
    "version": 1,
    "pause_policy": "freeze_on_encounter",
    "combos": [
      {"id": "duo_guard", "members": ["jeanne", "margot"],
       "modes": ["TACTICAL_CT", "RPG_TURN"]}
    ]
  }
}
```

## Headless API

- `GameSession.party_orchestration_state(combat="RPG_TURN")` returns a detached active roster, leader, formation, eligible combo IDs and pause policy.
- `GameSession.party_switch_leader(hero_id)` and `GameSession.party_set_formation(slots)` validate and append one event atomically.
- `GameSession.party_set_active(...)` commits R41+R53 together or not at all. The leader survives if still active; formation resets deterministically after group changes.
- `GameSession.recording()/from_recording()` adds `party_orchestration` only when enabled. A configured session missing the mandatory R53 checkpoint is rejected.
- `GameSession.rpg_start(...)` projects eligible executable R53 specs into the existing `ClassicEncounter`. `GameSession.rpg_action({"kind":"combo", "actor": "jeanne", "target": "enemy_id", "combo": "combined_strike"})` is a normal replayed command. The R41 Player facade also accepts `rpg_action("combo", target="enemy_id", skill="combined_strike")` (the `skill` argument names the combo ID for this compatibility entry point). The Player UI is not yet a visual R53 Party Composer.

## Reproducible test commands

```sh
python -m unittest -v tests_standalone.test_r53_party_orchestration tests_standalone.test_r53_combo_rpg
python -m unittest -v tests_standalone.test_r41_classic_party tests_standalone.test_r41_encounter tests_standalone.test_r41_routed_encounter tests_standalone.test_game_session tests_standalone.test_r25_foundation
```

Dedicated GitHub workflow requests Python 3.12 on Ubuntu, Windows and macOS. **No green CI, visual/Qt, export or hardware certification is presumed without actual logs.**

## Remaining NO-GO

R53.A2 delivered partially for **RPG_TURN only**: native two/four-hero offensive skills, validated MP, helper turn recovery, replay/restore and legacy R41 compatibility. **Still NO-GO** for CT and ACTION_REALTIME execution, defensive/healing combos, per-tick pause across action scenes, R43 merged integration and real Player UI.
R53.B: Party Composer Qt, placement, preview, undo/redo, user input evidence.
R53.C: hybrid exploration→tactical→exploration with canonical HP/inventory/rewards, three companions, two combat modes, two seeds and crash-save/reload.
Other dependencies: R41, R43, R51 and R50 gates still need proof on `master`.

## R53.A2 — executable native RPG_TURN combo example

The optional `skills` mapping makes an authored combination executable **only** in R41's existing RPG encounter, with a native enemy-target damage skill for every listed member. An R53.A1 combo without `skills` remains view-only.

```json
{
  "id": "combined_strike",
  "members": ["jeanne", "etienne"],
  "modes": ["RPG_TURN", "TACTICAL_CT"],
  "skills": {"jeanne": "estoc", "etienne": "garde_rapprochee"}
}
```

- This does **not** authorize a combo in CT: the `TACTICAL_CT` mode remains a declarative future capability. The runtime executor is `RPG_TURN` only.
- Only the first member can initiate, on their own RPG turn. Every member must be active, alive, ready and able to pay the cost of their own native skill. The target must be a living enemy.
- The existing R41 `_hit` and skill cost handling are reused. Helpers consume their next RPG activation. No separate combat/reward/HP database is created.
- Legacy encounters without executable combos emit exactly the historical R41 view fields; R53-enabled executable encounters include read-only `combos` and `combo_skip` fields inside the replayed view.
- Failures do not partially consume MP/inventory because `GameSession.rpg_action` commits only a verified candidate encounter. Saved combo commands are replayed from canonical authored skills; checksum-only tampering is rejected.
- Player QML buttons, remapping/assistive controls, video/on-screen testing, R53.B and R53.C remain outstanding.
