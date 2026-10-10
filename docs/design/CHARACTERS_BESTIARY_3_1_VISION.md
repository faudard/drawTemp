# 3.1 — Character, Bestiary & Progression 2.0
## Comparative review and revised design specification (2026-10-10)

**State:** design proposal, not delivered gameplay. Supplements the prototype in PR #42.
**Game:** Jeanne d'Arc — Les Cendres du Royaume, historical-alternative tactical RPG.
**Existing foundations:** Unit / ActorFactory / Content v1; Character & Rules Studio;
HeroProgress with campaign XP, job XP, learned talents and JP; equipment; ruleset 2.7
with coordinated AI and formations, tactical CT, deployment and deterministic replays.

## 1. Why the prototype needs a redesign

The initial 17-entry medieval pack proves that the existing content schema can load
and place wolves, bandits, squires, spearmen, knights and a 2x2 siege creature.
That is useful infrastructure, **not** a finished bestiary.

Current shortcomings:
- A catalog `role`, `family`, `tier` and description do **not** alter combat.
- Wolf/alpha/bandit role tags alone do not imply a pack or coordinated policy.
- Normal/veteran/elite ranks are mostly HP/stat multipliers, not new techniques.
- Equipment is additive bonuses; identity of weapon and tactical trade-offs are poor.
- Job changes and talent costs exist, but meaningful secondary-job ability loadouts,
  combat mastery, growth choices, injuries and origin traits are absent.
- `Campaign.finish` awards fixed 100 XP and 50 job XP to every player unit on
  a first victorious completion (no contribution, scenario or training distinction).
- A mission spawn and a persisted playable companion lack explicit identity and
  participation links. Do not implement permanent losses until this is solved.
- Content is not organized by narrative reveal: mundane enemies in early acts,
  supernaturals much later.

### Inspiration references
- **Final Fantasy Tactics**: more than 20 jobs, cross-job abilities and a build layer
  https://eu.finalfantasy.com/news/993
- **Battle Brothers**: personal origin, traits, equipment techniques, morale,
  durable wounds, tactical enemies
  https://battlebrothersgame.com/features/
  https://battlebrothersgame.com/dev-blog-18-character-traits-and-backgrounds/
  https://battlebrothersgame.com/dev-blog-20-bravery-morale/
- **Unicorn Overlord**: squad formations and explicit conditional tactics
  https://unicorn-overlord.com/en/
- **Wartales**: recruitable specializations and personalities
  https://wartales.net/game/
- **Darkest Dungeon**: persistent physical/mental consequences (use sparingly)
  https://www.darkestdungeon.com/darkest-dungeon/
- **Jeanne d'Arc (Level-5)**: historical-fantasy pacing and exceptional heroic forms
  https://www.jeuxvideo.com/news/2006/00018705.htm
- **D&D 4e encounter roles**: artillery, brute, controller, lurker,
  skirmisher, soldier; encounter composition instead of HP inflation
  https://index.rpg.net/display-entry.phtml?editionid=11496

Do not duplicate these games' protected visuals or data. Extract systems principles.

## 2. The design rule: no palette swaps

Every authored archetype needs **one readable tactical role**, **one distinctive
player-facing response**, **one AI intention**, and **one counterplay opportunity**.
Examples:
- Wolf / wolf alpha: flank or isolate / call a regroup; protect a separated ally,
  deny flank routes, pressure the alpha.
- Spearman: reserve a control zone and brace for a charge; turn his spear away,
  dislodge, outrange or attack from another direction.
- Crossbowman: powerful shot and a telegraphed reload; use cover and his reload window.
- Bandit captain: rallies allies; force surrender by isolating captain or breaking morale.
- Siege troll: occupies 2x2, telegraphs gate charge; disrupt charge or divert it
  towards another obstacle. Fantasy creatures must be act-gated.

**Role is not rank.** Separate combat role (skirmisher/guardian/artillery/leader)
from challenge rank (regular/veteran/elite/champion) and from social rank
(squire/knight/captain).

## 3. Character composition model (authoring, not yet runtime)

Think of a campaign actor as components rather than a single mutable archetype:

```text
ActorDefinition (stable type_id; authoring template)
  ├─ species / physical footprint / movement capabilities
  ├─ combatRole + faction + doctrine + ability packages
  ├─ baseline stats + weapon families + loadout constraints
  ├─ progression profile (playable companion, regular enemy, leader, beast)
  └─ presentation (portrait, body kit, equipment appearance, voice, animation)

ActorInstance (stable actor_uid; save/progression identity)
  ├─ definition_id + resolved base snapshot + origin + personality traits
  ├─ current_job + job_mastery + persistent learned techniques + loadout
  ├─ relations + deeds + wounds + morale + availability
  └─ campaign flags / recruit status / mortality policy

EncounterSpawn (per mission; short-lived battle identity)
  └─ actor_uid? + spawn_id + team + position + difficulty modifier + scenario state
```

Definitions can be updated in Studio without silently rewriting existing saves,
missions, replays or authored instances. Migration must be explicit and previewable.
Do not persist redundant derived stats or copy all instance fields to a separate
unvalidated sidecar.

Ruleset should remain the authoritative execution layer. The pure authoring pack
is projected into validated `Content` + a versioned, optional campaign-actor
extension. No Python scripts embedded in data. For behavior, use declarative
conditions/priorities resolved by a registry.

## 4. Six character dimensions

1. **Origin**: peasant, artisan, noble, soldier, deserter, healer, etc.
   Starting tags, practical skill and limited stat modifiers.
2. **Training/class**: a DAG of disciplines rather than an ever-longer list of
   linear upgrades. Skills learned from a class can optionally be slotted across
   jobs subject to explicit capacity and weapon restrictions.
3. **Personality/traits**: 0-2 initial significant traits; possible changes via
   events. Positive and negative, with understandable effects; avoid arbitrary
   tiny modifiers.
4. **Personal growth**: unit XP; job mastery; weapon or action mastery (bounded);
   story achievements independent of job mastery.
5. **Equipment**: stat tradeoffs, reach, guard break, movement/fatigue, recovery,
   reload and defensive tactics. These must have real battle semantics before UI.
6. **History**: wounds (optionally permanent), bonds, rivalries, decisions,
   recruitment and titles. Protect key story companions from contradictory
   death paths via explicit policy.

### Growth decisions
Retain existing campaign XP and class XP initially. Introduce additional growth
only when it changes a decision; prefer 2-3 visible choices per meaningful
level-up rather than dozens of pseudo-talent modifiers.

Example recruit path:
```text
Recruit
├─ Squire
│  ├─ Swordsman ─ Duelist / Master-at-arms
│  ├─ Guard ─ Knight / Standard-bearer
│  └─ Spearman ─ Pikeman / Sergeant
├─ Archer ─ Sharpshooter / Skirmisher
├─ Scout ─ Ranger / Pathfinder
└─ Healer ─ Field medic
```
Social elevation to the rank of knight is a narrative entitlement; a job
label alone must not grant a hereditary title or contradict story.

## 5. Combat roles and encounter composition

Role catalog:
- **Guardian/solider**: controls lanes, covers ally, resists displacements.
- **Skirmisher**: moves around edges, attacks isolated targets, disengages.
- **Ambusher**: waits in concealment and reveals an attack window.
- **Artillery**: high-value shots, weak when engaged, visible reload or cast.
- **Brute**: strong slow telegraphed strikes, can be interrupted.
- **Controller**: creates movement hazards and limits tactical choices.
- **Leader**: plans regroup, rallies morale, calls reserves.
- **Support**: triage, shields, logistics or buffs (strict cooldown/cost).

Initial narrative tiers:
- **Act 0–I:** wolves, war dogs, poachers, militia, bandits, mounted couriers,
  squires, sergeants, archers, crossbowmen, spearmen. No visible high fantasy.
- **Act II–III:** trained knights, formations, siege engineers, captains,
  partisan/mercenary militias, warhorses and specialist units.
- **Act IV–V:** rare corrupted variants and supernatural threats including
  optional multi-cell creatures, with explicit progression flags.
All factions include multiple military roles; avoid a faction=alignment shortcut.

A bandit ambush should test a different decision than a disciplined garrison;
composing roles is more important than writing 200 nearly-identical templates.

## 6. Readable doctrine-driven AI

For every actor, evaluate legal candidate commands deterministically:
- **Hard constraints**: CT, range, line-of-sight, occupancy, movement, statuses.
- **Doctrine**: e.g. `pack_hunt`, `protect_ranged`, `hold_gate`, `ambush_retreat`.
- **Intent**: transparent reason, predicted target and affected area, activation
  forecast. Can preview without mutating battle.
- **Utility scoring**: visible tie-break semantics, seeded RNG only through
  battle-owned deterministic state if needed.
- **Team objective**: danger, ally support, morale and formation constraints.
- **Counterplay**: the next threat must be sufficiently advertised to the player.

Test by exact ordered command predictions against known battle situations, not
only static role tags.

## 7. Morale and injuries without tedious micromanagement

Morale is a **small finite-state machine**: `steady`, `shaken`,
`wavering`, `routing`; `inspired` optionally as positive extreme.
Triggered by objective losses, isolations, leader death, encirclement and
rallies. An isolated bandit can surrender; a disciplined guard may stand.
Use direct, visible events and never silently cancel a player's order.

Wounds: introduce as opt-in campaign settings first (off/light/serious).
Temporary damage or a selected lasting scar can affect mechanics and narrative.
Important story actors must have an authored incapacitation fallback (rather
than corrupting future mission prerequisites). Never make irreversible save
decisions during battle replay verification.

## 8. Progression, attribution, balancing

Current reward `100 hero XP + 50 job XP` to all player mission units should be
treated as a compatibility baseline. Proposed versioned award ledger:
- once-only mission completion XP;
- bounded personal contribution XP with assist/defense/healing/objective support
  counted explicitly from battle events;
- optional training XP for benched heroes and story rewards;
- separate controlled unlock ledger for rank/titles/rare techniques;
- data-driven level curve and anti-farming rules (repeat battle identity);
- XP gains previewable before save, recorded once, and replay deterministic.

Avoid exploit incentives such as dragging fights out to farm healing or exploiting
free attacks. Measure time to first meaningful promotion, specialization and
skill without turning CT combat into repetitive grinding.

## 9. Studio UX target

```text
Personnages & bestiaire 4.0
  Catalogue   [Search] [Human | Beast | Supernatural] [Act] [Role] [Faction]
  Fiche       Identity | Stats | Equipment | Combat abilities | AI | Evolution
  Evolution   class DAG / mastery / traits / origin / unlock conditions
  Doctrines   graph: Trigger → Condition → Action → Priority / Intent preview
  Rencontres  Squad composition / difficulty budget / counters / reinforcements
  Test        Simulate, inspect enemy intentions, change seed, compare recordings
```

Create one true bestiary entry editor and reuse its definitions for both enemies
and recruitable companions. Allow copying a template as a *new, explicitly named*
definition. No raw JSON required for routine authoring. Editing and deleting
must be transactional with references checked; show impact/diff before propagation.

## 10. Proposed PR gates and sequencing

### P0 — 3.1.1 Base pack (existing PR #42; keep isolated)
Validated opt-in template library, placement, actor snapshots and
class-switch persistence. Update descriptions so catalogue roles are not
misrepresented as active runtime AI. Keep PR draft until all CI jobs are green.

### P0 — 3.1.2 Tactical archetypes & doctrines
Implement 4 authentic behaviors with end-to-end simulations:
wolf pack flanking, bandit ambush/retreat, spear lane control,
crossbow shoot/reload/protection.
Gate: 4 small encounters where changing the enemy mix changes
battle decisions; intents and counterplay visible; replay digest stable.

### P0 — 3.1.3 Distinct companion growth
Origin + 2 traits; class DAG and secondary skill loadout;
award ledger + real combat attribution; no double rewards.
Gate: two level-5 squires with distinct builds and biographies have
different legal battle choices, and survive save/load/undo where applicable.

### P1 — 3.1.4 Morale and campaign consequences
Finite states, rout/surrender, injuries, relationship milestones,
recruit/departure (narrative safety and mortality policy).
Gate: enemy surrender alters a branch or recruitment result and persists.

### P1 — 3.1.5 Character & Bestiary Studio 4.0
Integrated catalogue/trait/AI/progression graphs and encounter simulator.
Gate: author wolf pack + trained garrison + companion progression
without editing JSON, play, save, load and deterministically replay.

### P1 — 3.1.6 Balance & vertical slice
Three consecutive encounters:
(1) Jeanne's village, (2) forest ambush or rescue,
(3) castle approach with layered defenders.
Gate: 3-6 playable actors; no 300-unit micromanagement; enemy roles readable;
combat durations and level milestones measured; CI Python 3.10–3.14 on
Ubuntu/macOS/Windows plus Tk GUI smoke.

## 11. Explicit non-goals until later

- No giant initial catalog of 100 low-effort palette swaps.
- No copy of trademarked character designs.
- No 20 simultaneous status bars or unrecoverable story softlocks.
- No break of current mission snapshot semantics / `Content v1` by default.
- No enemy AI that secretly ignores CT, line-of-sight or footprint legality.
- No change to the game's canonical historical-fantasy pacing.

## 12. First deterministic scenario for acceptance

**The wolves of the forest:** Jeanne, a squire and an archer face three wolves
and an alpha. Player-readable predictions should show one wolf threatening the
isolated archer while the other blocks retreat, and an alpha coordinating.
Player can counter by grouping, covering the archer, or forcing the alpha
away. On alpha rout or death, the pack changes policy. Neither the foresight
preview nor repeated AI scoring can mutate the ongoing battle state.

**The brigand roadblock:** two melee bandits, a hidden archer, a captain, and a
civilian objective. Leadership loss changes morale. A surrender or rescue
changes the narrative without requiring every opponent be killed.
