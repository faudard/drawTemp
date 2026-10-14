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

## R6.14 — Tactical Choice Evidence

`sporebound.tactical_choice_lab_r6` samples real canonical Battle states
during a deterministic run. At each sampled Player command it attempts a
bounded set of actions against **isolated Battle clones**, calling
`Battle.execute` to confirm the alternatives are legal. It detects:
- meaningful positioning changes (cover, hazard, objective distance or
  distance to opponents), rather than counting every empty click;
- positive-chance basic attacks, executed by the rules engine;
- legitimate guard/overwatch preparations under enemy threat;
- relevant healing/MP or revival consumables and costly skills;
- nearby authored interactions, validated by Battle.

The report has actor ID, command index, chosen command, representative
alternatives with reasons, option categories, a fixed seed and a replay
digest. It never chooses a different action for the simulated AI or modifies
the authored Content.

`evaluate_choice_gate` refuses zero player samples or unverified replays,
allows a minimum count of multi-category states, and optionally requires
`positioning+damage`, `positioning+protection`,
`positioning+resources` or `positioning+objective` pairs. A failed pair
is **actionable design evidence**: it may be expected for an introductory
battle, but cannot be claimed as passing the richer encounter gate.

```sh
python -m sporebound tactical-choices --mission garden --seed 1 \
  --limit 120 --choice-min-multi 1 \
  --choice-required-pair positioning+damage \
  --report tactical-choices.json
```

Use the same mission, seed, sample stride and command cap when
comparing two versions. `compare_choice_reports` flags disappearance
of formerly available category pairs, excessive loss of multi-category
opportunities, and digest drift with unchanged authored inputs. Changes in
content/rules are disclosed; sampled decision states do not necessarily
represent identical tactical situations.

```sh
python -m sporebound tactical-choices --mission garden --seed 1 \
  --limit 120 --choice-min-multi 0 --report before.json
python -m sporebound tactical-choices --mission garden --seed 1 \
  --limit 120 --choice-min-multi 0 --baseline before.json
```

CLI exit codes: **0** for a passed coverage gate, **2** for an unmet
coverage gate, **1** for invalid arguments or source content. CI includes
a non-policy smoke check with `--choice-min-multi 0`; this does NOT
certify the complete design requirements for any shipped mission.

Within Studio → Balance Matrix, select a measured scenario and click
**Tester alternatives tactiques**. The displayed strict R6 profile
additionally asks for positioning-vs-attack/protection/resources. Export
the report locally using **Exporter choix R6**.

Coverage is **sampled**, not an exhaustive game tree, and still cannot
establish player satisfaction, informed trade-offs or a 15–30-minute
duration. Confirm these through real human playtests.

## R6.15 — Tactical Quality and Human Release Gate

**Why R6.15:** R6.14 proves that different commands are executable. It
cannot prove that those commands produce meaningfully distinct outcomes or
that real players understand the trade-offs.

### Counterfactuals measured from the same Battle state

`sporebound.tactical_quality_r6` observes bounded selected player commands
during a real, deterministic AI simulation. It executes the chosen command
and each R6.14 representative alternative **exactly once**, each against its
own copy of the same pre-command `Battle`, without modifying the main
simulation. Reports contain direct evidence, never a fabricated universal
action score:

| Benefit indicators | Resource / damage costs |
| --- | --- |
| Enemy HP removed, ally HP restored | Ally HP lost |
| Cover gained, hazard avoided | MP spent, consumables consumed |
| Distance to authored goal reduced | No automatic CT → minutes conversion |
| Prepared guard/overwatch states created | Preparation is not confirmed damage prevented |
| Objective hold ticks actually advanced | No prediction of future AI strategy |

A state is **differentiated** only if executable alternatives have different
immediate outcome vectors. A **trade-off** is counted only when both options
consume the **same exclusive movement or action slot** and neither wins on
all observed dimensions: one improves at least one property and sacrifices
another. This avoids falsely calling a move versus a subsequent attack an
opportunity cost when the engine allows both in one activation. It is a
Pareto-style local comparison, **not** a complete turn simulation, proof of
optimality, complete game tree or equivalent end-of-turn value.

### Dual release requirement

1. **Automated gate:** replay digest verified; enough player samples with
   distinct immediate consequences and observable trade-offs.
2. **Human gate:** opt-in report from the **same authored content hash**;
   enough complete, non-partial human sessions for the exact mission and
   variant; actual median playtime in the **15–30 real minute** design
   window; confusion annotations reviewed; and explicit approval of five
   criteria: positioning, protection, resources, objectives and player
   comprehension. Missing evidence remains **PENDING**; automation never
   manufactures human signoff.

Minimum complete observations default to five. This is a minimal review
threshold, **not a statistical power calculation** or proof of balance.
Real player comments, challenge and accessibility remain product review
criteria. No personal identifier or free-text feedback is required by the
instrumentation.

### Studio

In **Balance Matrix**, run a case and select its row, then:

1. **R6.15 · Mesurer les compromis** — collect canonical single-command
   effects, distinct choices, trade-off evidence and replay verification.
2. **Revue humaine R6.15** — select an opt-in human report and optional
   categorical R6.11 annotations; explicitly check the five human review
   criteria in the dialog. The human gate stays pending otherwise.
3. **Exporter qualité R6.15** — save reproducible evidence and any locally
   completed review, without writing to Content/GameProject or savegames.

Human evidence must match the content fingerprint. For annotated variants
enter the exact label in the review dialog; an unannotated report uses the
`authored` variant by default.

### CLI and CI

```sh
python -m unittest tests_standalone.test_tactical_quality_r615 -v
python -m unittest tests_standalone.test_full_activation_r616 -v
python -m sporebound tactical-quality --mission garden --seed 1 \
  --limit 120 --quality-min-differentiated 1 \
  --quality-min-tradeoffs 1 --report quality.json

# Release evidence: local opt-in human observations and explicit review
python -m sporebound tactical-quality --mission garden --seed 1 \
  --limit 120 --quality-min-tradeoffs 1 \
  --human-playtest human.json --quality-annotations annotations.json \
  --human-signoff signoff.json --report reviewed.json
```

`signoff.json` is a plain object containing *exactly* five booleans:
`positioning`, `protection`, `resources`, `objectives` and
`player_comprehension`. Every value must be consciously confirmed,
not generated from simulation data.

The **automated-only** CLI returns 0 if technical checks pass, but its output
explicitly says `not_certified_without_human_review`. When human evidence
is provided, it returns **2** if the release gate is incomplete.
CI uses a non-policy smoke sample and does **not** claim a human signoff.

## R6.16 — Full Activation Evaluation

R6.15 compares single legal commands. **R6.16** compares the consequences
of a **complete player activation**, using only the existing engine's
`Battle.execute`, `choose_command` and `End` boundary:

- real AI-selected reference activation (bounded to five commands);
- immediate `End`, attack/support/item/defense then `End`;
- cover/objective/approach move then `End`;
- move then a freshly legal attack/support/interaction then `End`;
- attack then move then `End` when both actions remain legal.

Every candidate starts from a **deep copy of the same live tactical state**
and independent, identically initialized random generator. Paths, reactions,
terrain, delayed effects, resources and CT are resolved by canonical rules.
The `end_turn` event is the authoritative boundary: a fast hero may become
active again after automatic CT advancement, but that is not an additional
command in the measured turn. The metric `ct_end_cost` is the actual cost
recorded by the rules, not a wall-clock estimate.

Candidate generation is intentionally **bounded** to 12 valid plans and
three movement anchors per decision, with a maximum of six sampled
activations per simulation. It does not prove that all moves, skills or
multi-front consequences were explored. Terminal branches keep an explicit
result and are **not** compared against nonterminal branches using an
arbitrary victory-to-damage conversion.

For nonterminal branches, the report contains after-End HP, heals, resource
consumption, cover, hazard, goal distance and CT cost. It describes the
**Pareto frontier**: an alternative is dominated only when another is no
worse on all measured dimensions and strictly better on at least one.
The report also counts non-dominated pairs that actually differ; it never
manufactures a single tactical quality score. This does not predict how
the enemy will behave during subsequent turns.

### Studio workflow

In **Balance Matrix**, run the baseline/variants, select a case and use
**R6.16 · Tours complets**. The analysis uses the **same immutable authoring
snapshot, rules, initial inventory and seed as the selected Matrix case**,
not a later modified Studio document. The panel presents the sampled
`Move → Act → End` and `Act → Move → End` sequences, CT end costs and
measured consequences. **Exporter tours R6.16** writes the complete
reproducible JSON.

### Headless gate

```sh
python -m unittest tests_standalone.test_full_activation_r616 -v
python -m sporebound full-activation --mission garden --seed 1 \
  --limit 120 --activation-min-distinct 1 \
  --activation-min-pairs 1 --report full_activation.json
```

Exit code 0 means *technical sample coverage achieved*; 2 means an
unmet automated gate, 1 indicates malformed inputs. The CLI explicitly
states `human_certified: false`, and the opt-in human review criteria from
R6.15 remain mandatory for release. CI runs a limited technical smoke
with zero optional coverage thresholds and does not claim player quality.

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
python -m unittest tests_standalone.test_tactical_choice_r6 -v
python -m unittest tests_standalone.test_tactical_quality_r615 -v
python -m unittest tests_standalone.test_balance_matrix_382 -v
python -m unittest tests_standalone.test_playtest_384 -v
python -m unittest tests_standalone.test_battle_diagnostics_381 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest \
  tests_standalone.test_balance_matrix_382_gui \
  tests_standalone.test_playtest_384_gui -v
```

CI runs on supported Python 3.10/3.12/3.14 and three operating systems.
Human playtests and Studio usability require separate sign-off.
