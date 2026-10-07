# Sporebound Tactics — Combat Design 1.0

Status: design target for the standalone engine. This document is normative for future gameplay PRs unless superseded by a later decision log entry.

## Product statement

Sporebound Tactics is a solo tactical JRPG built around compact grid maps with elevation, individual CT initiative, strong positional play, terrain interaction, readable delayed actions, and a campaign of authored tactical objectives.

The core design equation is:

**Time × Position × Terrain × Build × Objective**

A new mechanic should materially strengthen at least one of these axes. Mechanics that only add arithmetic without changing decisions should be rejected or simplified.

## Desired player experience

A strong turn should make the player answer several questions at once:

- What happens before this unit acts again?
- Which tile changes the tactical situation rather than merely shortening distance?
- Can terrain, elevation, facing or forced movement create a better outcome?
- Which resource or build choice is worth committing now?
- Does the mission objective make a locally strong attack strategically wrong?

The game should reward planning, adaptation and creative combinations rather than rote damage optimization.

## 1. Time: keep the CT model

The current standalone engine keeps the valuable Final Fantasy Tactics idea that doing less now can buy earlier access to the next activation.

Target rules:

- units accumulate CT from Speed;
- an activation starts at CT >= 100;
- Move + Act costs more CT than Move only / Act only;
- Wait is the cheapest end state;
- excess CT is preserved with a cap;
- delayed actions resolve on the same world clock;
- Haste/Slow and cast speed act on this shared temporal model.

This is a **KEEP**.

The design consequence is important: "use every action every turn" must not always be optimal.

### Required presentation

The original inspiration exposes future timing through an AT list. Sporebound should go further:

- visible upcoming activations;
- projected cast resolution inserted in that timeline;
- preview of how Wait / Move / Act changes the next activation;
- clear interruption/cancellation conditions;
- no hidden initiative modifiers in ordinary play.

## 2. Position: make space a first-class resource

Position is not just range checking.

Required spatial dimensions:

- cardinal movement and weighted paths;
- elevation and jump limits;
- facing;
- rear/side/front consequences;
- line of sight;
- threat/reaction zones;
- forced movement;
- adjacency and formations;
- objective pressure.

The player should regularly choose a weaker attack because the stronger positional outcome is more valuable.

## 3. Terrain: move beyond passive tiles

Triangle Strategy and Into the Breach show that terrain becomes tactically valuable when actions can transform the board or exploit geometry.

Core terrain interactions to support:

- push / pull;
- knockback fall damage;
- hazards;
- destructible or toggleable blockers;
- doors, switches and bridges;
- persistent zones;
- elemental or stateful tiles;
- temporary walls/obstacles;
- height-sensitive skills;
- objective tiles.

Future terrain effects should be composable rather than special-case scripted whenever possible.

Examples:
- fire can create a burning zone;
- water can conduct or amplify an electric effect;
- ice can reduce movement control or create slippery displacement;
- spores can modify movement, visibility or status exposure.

Exact elemental rules are not frozen by this document; composability is.

## 4. Build: constrained expression

A build should change *how* a unit solves tactical problems.

Preferred structure for future research:

- primary job/class;
- secondary action set or specialization;
- a small number of selectable passives;
- one reaction slot;
- one movement/support specialization;
- equipment slots with tactical, not merely numeric, identity.

This follows the useful constraint visible in FFT/Fell Seal-like systems: players combine systems, but cannot equip everything at once.

Avoid:
- dozens of low-impact +5% variants;
- mandatory passives that every optimal build takes;
- permanent stat growth traps that punish experimentation.

## 5. Objective: encounters need an intention

A mission is not "a map plus enemies".

Every authored mission must declare an **encounter intention**. Examples:

- cross exposed ground under ranged pressure;
- hold a chokepoint while the map changes;
- extract a slow carrier;
- rescue a unit before an enemy timeline event;
- capture two zones that cannot both be defended by one formation;
- defeat a caster whose delayed spells reshape safe space;
- recover an object and retreat rather than wipe the map.

Objectives currently supported by the engine (eliminate, survive, extract, hold, crown) are a good base. Future objectives should be justified by the decision space they create.

## 6. Information and randomness

Sporebound should not become fully deterministic, but important tactical information must be readable.

### KEEP
- hit chance;
- damage ranges or exact expected direct damage;
- status chances;
- CT order;
- cast timing;
- visible reactions when known;
- visible enemy threat ranges.

### ADAPT
Randomness should create adaptation, not invalidate planning.

Use RNG for:
- hit/evasion;
- selected reactions;
- optional status uncertainty;
- carefully bounded secondary effects.

Avoid RNG for:
- hidden initiative jumps;
- unexplained objective behavior;
- invisible terrain rules;
- arbitrary AI bonuses;
- large untelegraphed damage swings.

Forecast should explicitly distinguish:
1. deterministic result;
2. probabilistic branch;
3. future opponent-dependent uncertainty.

## 7. Reactions

Reactions are valuable because they make positioning and build choices matter outside the active unit's turn.

Rules:
- reactions cannot recursively chain without an explicit exception;
- each unit has a clear reaction capacity;
- threatening reactions are previewable;
- reactions should usually consume a reserve, slot, cooldown, resource or eligibility condition;
- Intercept/Guard should be explored before adding more passive retaliation variants.

Reaction spam that turns every action into an opaque cascade is a **REJECT**.

## 8. Mobility guardrail

Mobility can destroy encounter design if it bypasses geometry too cheaply. Fire Emblem Engage's developers explicitly describe this tension when increased movement and teleportation threatened to break stage tactics.

Therefore every exceptional mobility skill must pay at least one meaningful cost:
- CT/time;
- limited range or destination rules;
- resource;
- cooldown/charge;
- exposure;
- one-use/per-encounter limit;
- inability to carry an objective;
- predictable enemy counterplay.

Teleport is retained, but must be balanced against authored map topology.

## 9. Enemy design

Enemy variety should change decisions, not only stats.

Preferred archetypes:
- anchor/tank;
- skirmisher;
- artillery/caster;
- controller;
- support;
- assassin;
- objective runner;
- summoner/reinforcement source;
- terrain manipulator.

Each archetype should declare:
- desired range;
- positional preference;
- objective priority;
- synergies;
- vulnerabilities;
- signature threat.

The encounter designer should select combinations intentionally.

## 10. Battle size and pacing targets

Initial design target, to validate empirically:

- player squad: 4–6 active units;
- enemy presence: usually 5–10 simultaneously active;
- compact maps where meaningful contact occurs quickly;
- standard encounter: roughly 15–30 minutes once the final UI exists;
- tutorial/short encounter: 5–15 minutes;
- boss/set-piece encounters may exceed this deliberately.

These are targets for telemetry, not hard engine limits.

## 11. Non-goals for the next phase

Do not prioritize yet:

- zodiac compatibility;
- exhaustive FFT formula parity;
- dozens of jobs;
- renderer polish;
- procedural campaign generation;
- online multiplayer;
- complex permanent injury systems.

They can be revisited after the core loop is proven.

## 12. Definition of a good new mechanic

Before implementation, answer:

1. Which pillar does it strengthen: Time, Position, Terrain, Build, Objective?
2. What new decision does it create?
3. What existing decision does it risk making irrelevant?
4. Can the player understand its consequence before committing?
5. Can AI evaluate it using the same rules?
6. Can the editor author and validate it without custom code?
7. Can headless simulation measure its effect?
8. Does it compose with at least two existing systems?

If these answers are weak, reject the mechanic.

## Research basis

Primary/industry sources and bibliography are tracked in:
- `docs/research/BIBLIOGRAPHY.md`
- `docs/research/COMPARATIVE_ANALYSIS.md`
- `docs/research/DECISION_LOG.md`
