# Sporebound Tactics — Decision Log

Each decision records what is currently accepted, adapted or rejected. Future PRs should reference these IDs when they intentionally alter combat fundamentals.

## D-001 — Standalone deterministic rules core
**Decision:** KEEP.

Battle rules remain independent from renderer/editor. Player, AI, replay and tests use the same command boundary.

**Reason:** enables reproducibility, headless simulation, tool independence and future renderer/platform changes.

## D-002 — CT-based individual initiative
**Decision:** KEEP.

Preserve Speed-driven CT, activation threshold and different CT costs for Move+Act vs partial/Wait turns.

**Reason:** creates a meaningful time economy and makes restraint tactically valuable.

## D-003 — Visible future timeline
**Decision:** ADD.

Expose expected unit activations and delayed-action resolution. Preview how the current command changes future timing.

**Reason:** CT is strategically valuable only if players can reason about it.

## D-004 — Move + Act in either order
**Decision:** KEEP.

Do not force move-before-action or action-before-move globally.

**Reason:** increases tactical options and works naturally with CT and positional play.

## D-005 — Elevation, facing and LOS
**Decision:** KEEP and deepen.

Height must affect more than decoration. Facing should matter selectively, not on every mechanic.

**Reason:** this is one of the project's strongest spatial differentiators.

## D-006 — Forced movement and falls
**Decision:** PROMOTE TO CORE.

Push, pull, displacement and fall consequences are not secondary skill gimmicks; they are a central combat family.

**Reason:** they connect Position + Terrain and create non-damage solutions.

## D-007 — Stateful/composable terrain
**Decision:** ADD incrementally.

Prefer generic tile state/effect composition over mission-script-only special cases.

**Reason:** supports systemic play, editor analysis and AI evaluation.

## D-008 — RNG
**Decision:** ADAPT, not remove.

Keep bounded hit/status/reaction uncertainty but make probabilities and consequences visible.

**Reject:** large hidden random swings that invalidate planning.

## D-009 — Forecast
**Decision:** DEEPEN.

Forecast must become a first-class pure query API used by UI, AI and tests.

Future output should distinguish deterministic outcomes, probability branches, reactions and future uncertainty.

## D-010 — Reactions
**Decision:** KEEP WITH BUDGETS.

Reactions must remain readable, non-recursive by default and limited by clear eligibility/resource rules.

**Add before more reaction types:** Intercept / ally protection / threat preview.

## D-011 — Teleport and extreme mobility
**Decision:** KEEP WITH HARD GUARDRAILS.

Every exceptional mobility mechanic must pay a tactical cost and must not erase encounter topology.

**Reason:** Fire Emblem Engage's developers explicitly identify excessive movement as a risk to stage tactics.

## D-012 — Zodiac compatibility
**Decision:** DEFER.

Do not implement in the next combat-depth phase.

**Reason:** adds matchup arithmetic and opacity without strengthening the current weakest areas (encounter intention, terrain interactions, timeline readability).

## D-013 — Brave/Faith
**Decision:** REVIEW / ADAPT.

Current Brave/Faith can remain temporarily for prototype compatibility, but the final product must justify each stat with clear player-facing meaning. Avoid carrying FFT terminology purely for fidelity.

## D-014 — Build structure
**Decision:** TARGET constrained modularity.

Research target:
- primary job;
- secondary action set/specialization;
- few free passive slots;
- one reaction slot;
- movement/support specialization;
- meaningful equipment.

Do not freeze exact counts until the progression study.

## D-015 — Encounter intention
**Decision:** REQUIRED.

Every production mission will have a one-sentence tactical intention and validation criteria.

Example: "Cross the central low ground while two elevated ranged enemies force use of cover and displacement."

A mission that cannot state its tactical question is not ready for content production.

## D-016 — Objectives beyond elimination
**Decision:** KEEP and expand.

Prioritize escort/rescue, multi-zone control, timed escape, objective carrier, reinforcement pressure and secondary objectives.

## D-017 — Enemy archetype metadata
**Decision:** ADD.

Enemy definitions should expose role, desired range, terrain preference, objective priority and synergy tags for AI and encounter tooling.

## D-018 — Threat map
**Decision:** ADD before visual polish.

Threat should include:
- reachable attack cells;
- reaction danger;
- delayed cast danger;
- known forced-movement consequences where feasible.

## D-019 — Tactical editor direction
**Decision:** editor is an Encounter Designer, not a generic engine editor.

Long-term layers:
- topography;
- navigation;
- environment;
- deployment;
- actors;
- objectives;
- triggers;
- analysis;
- simulation;
- telemetry.

## D-020 — AI architecture
**Decision:** keep deterministic utility AI as the production baseline for now.

Next steps:
- normalize utility terms;
- role/profile data;
- influence/threat maps;
- objective-aware scoring;
- multi-unit coordination;
- explainable decision traces;
- fixed computation budgets.

Do not replace it with minimax/MCTS until measurement shows a real need.

## D-021 — Automated balancing
**Decision:** expand beyond win rate.

Record at minimum:
- result;
- battle duration/ticks;
- first casualty;
- per-unit damage/healing;
- skill usage;
- unused skills;
- resource consumption;
- movement heatmaps;
- objective progress;
- CT advantage;
- death locations;
- dominant build/action frequencies.

## D-022 — Visual renderer
**Decision:** DEFER as a production priority, not as a product requirement.

A player-facing vertical slice eventually needs a real renderer/UI, but rule quality and encounter design remain the current gate.

## D-023 — Design acceptance test for new mechanics
**Decision:** REQUIRED.

Any significant mechanic PR must document:
- pillar(s) strengthened;
- decision created;
- counterplay;
- information shown to player;
- AI evaluation path;
- editor representation;
- simulation metric;
- interactions with existing systems.

## Immediate research sequence

1. Combat fundamentals — this log.
2. Jobs/builds/progression.
3. Level and encounter design.
4. Tactical AI.
5. Campaign/meta-game.
6. Data model and authoring UX.
7. Simulation/balance methodology.
8. Renderer/player UX.


## D-024 — Team is a sixth combat pillar
**Decision:** ADD.

The combat model becomes **Time × Position × Terrain × Build × Objective × Team**.

Team covers explicit synergies, formations, engagement, assists, prepared reactions and coordinated tactical actions.

## D-025 — Engagement is core spatial control
**Decision:** ADD.

Melee identity must not be reduced to short attack range. Close-combat units exert an engagement zone even without an opportunity-reaction slot.

Leaving engagement only creates an attack when a relevant reaction/preparation exists.

## D-026 — Prepared reactions
**Decision:** ADD.

Vigilance/Overwatch and Guard spend Act now to reserve one bounded future response.

Prepared reactions:
- expire on the preparing unit's next activation;
- have explicit charges;
- may apply a CT tax;
- are visible/queryable by UI and AI;
- do not recursively trigger reaction cascades by default.

## D-027 — Ranged attacks use practical range + falloff
**Decision:** EXPERIMENT.

Ranged basic attacks may use LOS-scale maximum reach while retaining an optimal range and accuracy falloff. Being engaged penalizes ranged basic accuracy and Overwatch cannot be prepared while engaged.

Goal: make closing distance strategically valuable without arbitrary short caps.

## D-028 — Pincer is the first explicit Team Tactic
**Decision:** PROTOTYPE.

Two tactic-enabled melee allies controlling opposite sides of one target may generate a bounded follow-up.

The partner spends CT and the follow-up cannot recursively trigger normal reactions.

This is a framework proof, not final balance.

## D-029 — Tactical Bonds / hidden unlocks
**Decision:** DESIGN NOW, PERSISTENCE LATER.

Pair/trio tactics may unlock through:
- story;
- dedicated missions;
- repeated joint deployment/mastery;
- hidden event sequences and achievements.

The unlock engine must consume normalized battle events rather than hardcoded battle-rule branches.

See `docs/design/TEAM_TACTICS.md`.


## D-030 — Disengage converts melee control into action pressure
**Decision:** ADD.

An engaged unit may spend Act to prepare a safe withdrawal; its following Move ignores Opportunity and clears the state.

**Reason:** melee control should impose a meaningful opportunity cost without becoming a hard movement lock.

Future contact mechanics (Charge, Brace, Pursuit, Challenge) must preserve this counterplay principle.


## D-031 — Intercept makes melee protection active
**Decision:** PROTOTYPE IMPLEMENTED.

A close-combat unit may spend Act to protect one nearby ally from one eligible enemy hit. The response consumes its prepared charge and CT.

**Reason:** tank/protector identity should come from spatial protection decisions rather than passive HP/DEF alone.

## D-032 — Crossfire is a ranged Team Tactic
**Decision:** PROTOTYPE IMPLEMENTED.

Two prepared ranged bondmates with LOS from distinct vectors may create a bounded follow-up. Same-ray positions do not qualify; engaged shooters cannot contribute.

**Reason:** long range remains powerful but teamwork still depends on geometry, positioning and CT reserve.

## D-033 — Tactical Bond unlocks are event-driven
**Decision:** FOUNDATION IMPLEMENTED.

Campaign progression stores per-pair statistics plus known/prepared tactics. Unlock rules may compose mission requirements, cumulative stats and hidden ordered event sequences.

Examples include target-specific shared kills and same-target status → displacement → damage patterns.

**Reason:** secret/mastery unlocks must be authored as data over normalized battle events, never as character-specific branches in the combat engine.
