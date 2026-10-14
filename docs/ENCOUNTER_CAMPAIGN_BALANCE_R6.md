# R6 — Encounter & Campaign Balance 3.0

**Status:** implementation proposal; merge only when Linux/macOS/Windows CI
passes and human design reviews have been performed. Builds on the canonical
3.8 Battle Lab, Balance Matrix, Diagnostics and opt-in Playtest Lab.

## R6.8 — Encounter Profiles

`encounter_profile(content, mission_id)` describes the *actual* authored map,
objective, roster, equipment/weapon families and AI behaviours. **4–6 heroes
and 5–10 enemies** are design targets, not silently synthesized units or
runtime restrictions. Authoring variants are bounded `balance_matrix` cases:
unit stats, equipment, behaviour, map cover/hazard/cost/blocking, placement,
cloned reinforcements and player consumables. Every case operates on deep-copied
`Content`; canonical `Content.validate` rejects illegal variants.

Cloned reinforcements inherit an authored unit archetype but have a distinct
id and position. They do not introduce new AI, unit schemas or spawn events.
Changes to the map and team inventory are **simulation-only**, not saved
automatically to the Studio document.

## R6.9 — AI Decision Analytics

`trace_encounter_ai` delegates to the existing `trace_seed`, canonical
`simulate` and replay. The report counts decisions by team/kind, protective
reactions, goal occupation, CT objective progress and diagnostic findings.
Immediate backtracks and no-op moves are reproducible, **heuristic signals**:
they do not prove strategically poor AI choices. The stored trace gives
step-level evidence. Studio runs the selected matrix variant on a worker and
shows results in the same Balance Matrix tab.

## R6.10 — Regression Gates

`strict_regression_gate(before, after)` extends `compare_matrices`:
same ordered seeds and command budget, same mission/case ids, unchanged
scenario specifications and starting rules manifest, replay verification, and
existing configurable victory-drop, p95 commands/CT-growth and new-limit
thresholds. Modified rules or variant definitions require a newly approved
reference instead of a misleading PASS. Content updates can be evaluated
with these controls; their effect is reported by the existing matrix gate.
No conversion from CT ticks to minutes is permitted.

## R6.11 — Human Playtest Analytics

The existing **opt-in** local recorder measures real wall-clock seconds after
committed Player actions. The Playtest Lab can annotate each session with an
authored variant label, one categorical confusion tag and an abandonment
category. Labels are local and separate from saved games. Import/export
annotations binds them to the same report length and content hash; no
personal identifiers or free text are collected.

`human_variant_breakdown` compares victory, defeat, abandonments, objective
progress and actual p50/p95 minutes by mission and variant. Only *complete
non-partial* human sessions contribute to real duration statistics. The
15–30 minute target is marked **not yet verified** below five full human
observations per variant (configurable minimum), and is **not** an automatic
proof of enjoyable or fair play even above that sample count.

## R6.12 — Encounter Tuning Tools

From **Studio → Balance Matrix**:
1. Choose an authored mission and an existing unit.
2. Select a preset for stats, placement (X/Y), reinforcement, ranged weapon,
   AI behaviour, map cover/hazard or potion resources.
3. Add the scenario, select seeds and command budget, then run comparison.
4. Inspect p95, win deltas, unresolved encounters and a trace for that
   selected case; import an inter-revision baseline and inspect strict gates.
5. Export the report. No manual JSON editing, alternate rules, or Studio
   document/savegame mutation.

The variants are exploratory, not automatically committed back into the
authoring Content. Invalid cases fail explicitly, including map collisions,
illegal inventory or incompatible AI behaviours.

## R6.13 — Campaign Balance Progression

`campaign_balance_curve` deep-copies a real `Campaign`, then uses its
`prepare`/`finish` path, canonical simulation and verified Battle replay
for each requested mission and seed. The report contains actual awarded XP,
gold, equipment, wounds, inventory, unlocks, story flags and a heuristic
enemy/player *budget ratio*. If a mission is locked or not won, the run
records the obstruction and stops instead of granting fictional rewards.

Studio's **Parcours campagne R6** follows the first available authored
`next_missions` edge (up to eight missions) from the selected mission.
Users may choose a local Campaign save as the starting point or start a
fresh campaign. Other branches must be simulated separately: this is not
exhaustive path certification. The export contains the input/output
campaign snapshots for reproducibility without overwriting them.
`campaign_curve_review` flags abrupt budget increases for **human review**
rather than claiming measured difficulty from a numeric ratio.

## R6 design gate — tactical choices, not merely DPS

A release reviewer should check at least:
- viable positioning/cover routes and nontrivial opportunity costs of
  moving versus attacking;
- meaningful protection, reactions and ally support options;
- resource and equipment tradeoffs (consumables, MP, damage, survivability);
- encounter variety, objectives and paths through consecutive missions;
- paired determinism and regression thresholds at fixed seeds/rules;
- **real** human playtest evidence for encounter duration, confusion and
  abandonments before declaring a 15–30 minute target met.

Automated traces alone can show *what the canonical AI did*, not whether
every alternative was fair or fun. A missing playtest does not silently pass
the human-design gate.

## Validation

```sh
python -m unittest tests_standalone.test_encounter_balance_r6 -v
python -m unittest tests_standalone.test_balance_matrix_382 -v
python -m unittest tests_standalone.test_playtest_384 -v
python -m unittest tests_standalone.test_battle_diagnostics_381 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest \
  tests_standalone.test_balance_matrix_382_gui \
  tests_standalone.test_playtest_384_gui -v
```

CI runs on supported Python 3.10/3.12/3.14 and three operating systems.
Human playtests and Studio usability require separate sign-off.
