# Battle Lab 3.8 — Balance, Telemetry & Determinism

The Game Studio contains a **Battle Lab** tab (also accessible from the
project Workspace). It measures the *existing* `Battle` engine and
`ai.simulate()` decision loop. No alternate combat rules, objective evaluator,
persistent mission schema or savegame format are introduced.

## Studio workflow

1. Select a mission, a comma-separated list of independent RNG seeds and a
   command cap. Run **Simuler**; the Studio remains interactive while a worker
   evaluates an immutable content snapshot.
2. Inspect each seed's result, CT ticks, command count, activation count and
   possible stall marker. The detail view aggregates damage inflicted/received,
   healing received, reactions, survival by class/weapon, tactical AI decisions
   and per-seed objective progress.
3. Use **Référence = résultat courant** or **Charger référence JSON** before
   editing the encounter. Run the *same* seed set against the new rules/content.
   The paired delta and gate findings appear below the metrics.
4. Export the complete machine-readable, versioned JSON report for code review.
   **Afficher sur la carte** returns to the authored mission in the existing
   Map Editor. Simulations do not edit the Studio document or project.

## Command line

```sh
python -m sporebound battle-lab --mission garden --seed 1 --runs 20 \
  --limit 500 --report before.json
# Change rules, encounters, actors or AI and run the same seeds:
python -m sporebound battle-lab --mission garden --seed 1 --runs 20 \
  --limit 500 --baseline before.json --report after.json
```

A failing comparison returns process code **2**, suitable for a CI gate.
Defaults are a maximum **25 percentage-point** drop in win rate, **30%** growth
in p95 CT ticks or command count and **zero newly unresolved seeds**. Override
deliberately when authoring a harder boss or longer set piece:

```sh
python -m sporebound battle-lab --mission garden --seed 1 --runs 20 \
  --limit 500 --baseline before.json --max-victory-drop 0.35 \
  --max-p95-growth 0.50 --max-new-limits 0
```

Reports are paired by ordered seeds, mission and command cap, never by
unpaired averages. If both content hash and rules manifest are identical,
a differing canonical battle digest is a determinism regression. Every
current run must also pass actual `Battle.replay()` digest verification;
the old version of the CLI `balance` and the existing `balance3.evaluate`
remain available unchanged.

The CI now pins `docs/evidence/battle_lab_garden_38.json`: 8 seeds
(1–8), 500 commands/seed, default garden rules; the first baseline measured
2 automated victories, 6 defeats, 0 unresolved runs, p95 108 CT ticks and
132 commands. The CI **re-evaluates** those seeds and compares against the
committed JSON with a maximum 20-percentage-point victory-rate drop, 30%
growth of p95 CT ticks/commands and zero new unresolved seeds. Identical
input hashes additionally require identical final replay digests. It never
regenerates and silently accepts its reference on a changed ruleset.

**Important:** this is a regression reference, not a declaration that a 25%
AI-vs-AI victory rate is good human-player balance. Establish human playtest
objectives before approving any intentional changes to the pinned baseline.

## Telemetry meaning and limitations

- **Duration:** engine ticks and commands are deterministic proxies for
  pacing; they are *not* wall-clock performance or minutes of player time.
  Capture human session duration separately during actual playtests.
- **Classes:** an authored `class:` or `job:` tag is used first, then
  archetype, then weapon family (labeled `weapon:...`). This deliberately
  does not infer a character's purchased campaign job from a battle spawn.
- **Damage:** `received:<team>` credits HP lost to that team and
  `dealt:<team>` credits known damage sources. Environmental harm may have
  no source. Healing events currently expose the recipient but not the caster,
  so healing is reported **received by team**, not attributed to a healer.
- **Reactions:** instrumented canonical events include prepared attacks,
  interception, counters, pursuit and team tactics.
- **AI:** actor/team-scoped counts of the actual chosen command kind, not a
  hypothetical move ranking. The observer runs outside engine commands and
  makes no RNG calls or mutations.
- **Objectives:** objective ID, actual hold ticks, target ticks, occupied
  goal tile and victory outcome; these are diagnostics, not a fictitious
  normalized progress percentage across incompatible objectives.
- **Possible stall:** an unresolved seed with 30 consecutive commands lacking
  changes to positions, HP, objects or explicit objective state is marked for
  review. Some long-distance waits are legitimate; this is a heuristic,
  not proof of a deadlock. All unresolved seeds are counted separately.
- **Survival:** final survival per team and class, aggregated over runs.

## Gameplay design targets (advisory)

The authoritative [Combat Design 1.0](design/COMBAT_DESIGN.md) targets an initial
squad of 4–6 allied actors, commonly 5–10 active enemies and about 15–30
minutes **for standard human-played encounters**. These are not limits in
`Battle`, and the Lab must not misreport CT ticks as human minutes. Measure
them with representative testers before fixing a time-based acceptance gate.

## Reproducibility and gates

Run `python -m unittest tests_standalone.test_battle_lab_38 -v`. Under Xvfb,
set `SPOREBOUND_GUI_SMOKE=1` and run
`python -m unittest tests_standalone.test_battle_lab_38_gui -v`.

The required exit gate checks: same seeds, same command cap, identical repeat
runs on unchanged inputs, verified replays, a committed report baseline,
and no unapproved major drop in victory rate, p95 duration growth or unresolved
encounters. Human-session pacing targets must be validated by human players,
not fabricated from simulator timings.
