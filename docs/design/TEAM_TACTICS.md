# Sporebound Tactics — Combat 1.1: Engagement, Vigilance & Team Tactics

Status: design + first implementation target.

## Why this exists

The combat must not reduce melee to `range = 1`, ranged combat to arbitrary short caps, or team synergy to passive adjacency bonuses.

Combat 1.1 separates three concepts:

1. **Engagement** — persistent spatial control created by close-combat units.
2. **Prepared Reactions** — an active unit spends its action now to reserve a future response (Vigilance, Guard, Intercept).
3. **Team Tactics** — two or more allies satisfy positional, temporal, target or terrain conditions and unlock a coordinated action.

These systems extend the design pillars to:

**Time × Position × Terrain × Build × Objective × Team**

## 1. Engagement is not a reaction

A unit with a close-combat control zone exerts engagement around itself even when it has no reaction skill equipped.

Initial weapon control targets:

| Weapon family | Engagement | Intent |
| --- | ---: | --- |
| unarmed / dagger / sword | 1 | local control |
| spear / polearm | 2 | lane/chokepoint control |
| ranged / focus | 0 | requires protection or disengagement tools |

Engagement should be queryable by UI and AI.

### Consequences

Being engaged may affect:
- ranged accuracy;
- ability/cost to disengage;
- access to some abilities;
- Intercept/Guard relationships;
- formation bonuses;
- objective carrying;
- future charge/pursuit mechanics.

Leaving engagement **does not automatically mean a free attack from every melee unit**. Opportunity attacks remain a reaction rule. This prevents engagement from becoming reaction spam.

## 2. Melee must control space

Melee units need tactical authority, not only higher damage at distance 1.

Target mechanics:

- **Opportunity**: reacts when an enemy leaves engagement.
- **Guard**: prepare to strike/stop the next enemy entering the control zone.
- **Intercept**: protect an ally in or adjacent to the control zone.
- **Pursuit**: follow an enemy that disengages.
- **Brace**: resist forced movement and charges.
- **Challenge**: punish an engaged target for attacking another unit.
- **Reach**: spears control at distance 2.
- **Pincer**: coordinated melee placement enables a team tactic.
- **Backline pressure**: engaging a ranged unit degrades its ability to use long-range attacks freely.

The design objective is that "closing the distance" changes the tactical state.

## 3. Long-range combat: remove arbitrary caps where possible

Do not define ranged identity only through small Manhattan caps such as `range=4`.

Prefer three concepts:

- **maximum/physical reach** — may be map-scale for some weapons;
- **optimal range** — normal accuracy/effectiveness;
- **falloff / handling** — cost of shooting outside the optimum or while engaged.

Examples:

### Bow
- long practical range;
- good elevation interaction;
- moderate distance falloff;
- poor handling when engaged.

### Crossbow
- long range;
- high accuracy;
- larger CT/reload cost.

### Rifle
- very long line-of-sight reach;
- strong accuracy at distance;
- expensive time economy / reload / setup.

### Magic
- range may be large;
- constrained by cast time, MP, target lock, interruptibility, terrain and LOS.

### Spear
- engagement/reach 2;
- powerful lane control;
- weaker against adjacent flanking depending on final weapon model.

The key trade-off is not "the target is one tile beyond an arbitrary number", but "can I afford the time, exposure and accuracy consequences?"

## 4. Prepared Reactions

A prepared reaction is chosen as an action and creates a temporary reserve.

Initial framework:

### Vigilance / Overwatch
Spend Act to watch a legal reaction zone.

Trigger examples:
- enemy enters LOS;
- enemy enters weapon threat;
- enemy crosses a marked lane.

The response is a basic ranged attack or configured reaction skill.

Important constraints:
- one preparation has a finite number of charges;
- it expires at the preparing unit's next activation;
- reaction resolution is deterministic in ordering;
- it never recursively triggers another prepared reaction unless explicitly allowed;
- UI exposes the watched zone.

### Guard
Melee equivalent of Vigilance.

Spend Act to watch the engagement zone.

Trigger:
- enemy enters the zone, attacks an adjacent protected ally, or attempts a configured crossing.

### Intercept — IMPLEMENTED PROTOTYPE
Prepared protection rule. The current version protects one nearby ally for one eligible enemy hit, redirects the resolved hit to the protector, consumes the charge and applies the prepared-reaction CT tax.

Trigger:
- ally in protected space becomes the target of an eligible attack.

Possible resolution:
- protector becomes target;
- protector steps into the line;
- protector reduces damage;
- protector counterattacks.

Exact variant belongs to build/class identity.

## 5. CT cost of reactions

Prepared reactions must interact with Time.

Baseline experiment:
- preparing consumes Act normally;
- firing consumes the preparation charge;
- optionally apply a reaction CT tax;
- preparation expires when the unit next activates.

The CT tax should be data-driven so heavier reaction weapons can delay the next activation more than light reactions.

This makes a Vigilance choice a temporal investment rather than free damage.

## 6. Team Tactics

A Team Tactic is not simply "+10% attack when adjacent".

It should create a new tactical action, transformation or response.

Activation dimensions:

- **proximity** — allies within N cells;
- **formation** — pincer, line, triangle, shield wall;
- **LOS** — two allies can see the same target/zone;
- **target history** — ally just hit/statused/moved the target;
- **time** — both are ready or have enough CT reserve;
- **terrain** — target is inside a zone or at an elevation relation;
- **objective** — carrier/escort/defense context;
- **relationship** — tactic unlocked for the pair/trio.

## 7. Initial tactic families

### Follow-up
One ally creates an opening and another performs a bounded free/discounted attack.

### Pincer
Two melee allies control opposite sides of one target.

Potential outcomes:
- follow-up strike;
- reduced evasion;
- blocked disengagement;
- forced facing choice.

Prefer an explicit follow-up or control effect over a flat damage aura.

### Crossfire
Two ranged allies threaten the same target from meaningfully different angles.

Potential outcomes:
- second shot;
- suppress/mark;
- force movement.

### Launch / Relay
One ally moves another.

Examples:
- throw/boost an ally across a gap;
- swap positions;
- transfer movement;
- propel a melee unit into engagement.

### Protect
Two linked characters gain a special intercept/guard option.

### Combo Skill
Two known skills combine into a distinct technique.

Chrono Trigger is a useful reference: Double/Triple Techs require the relevant characters and learned techs, and the combined action is a distinct move rather than a hidden stat bonus.

### Terrain Combo
One unit creates state; another transforms it.

Examples:
- spores + fire;
- water + lightning;
- oil + fire;
- ice + forced movement;
- wall + push/fall.

### Temporal Combo
One character manipulates CT/cast timing so another action resolves in a new tactical window.

## 8. Tactical Bonds and unlocks

**Pair + trio foundation is implemented.** Campaign state persists statistics for groups of two or three, known/prepared tactics (initial limit: 2 per group) and battle ids already counted. Tactic arity is explicit, so pair techniques cannot accidentally be prepared as trio techniques.

Pair/trio tactics can be learned through multiple routes.

### Story unlock
- chapter event;
- relationship scene;
- mandatory tutorial mission.

### Mission unlock
- dedicated optional mission;
- character quest;
- challenge encounter.

### Mastery unlock
- complete N missions together;
- use a tactic family N times;
- reach job/skill prerequisites.

### Hidden emergent unlock — PAIR/TRIO FOUNDATION IMPLEMENTED
A pattern in real battles unlocks a tactic. The declarative evaluator supports cumulative stats, current/completed mission requirements, `all`/`any` composition, ordered event sequences with a tick window, same-target constraint, participation by every group member and a repeat `count`. Non-overlapping matches prevent one event chain from satisfying the same repeated secret several times.

Examples:
- protect the same ally from lethal damage three times;
- defeat several heavy enemies together;
- repeatedly push enemies into an ally-created hazard;
- win while both characters are critically wounded;
- execute a specific status → displacement → fall sequence;
- kill a boss with both characters participating.

Hidden unlocks should be discoverable after the fact through hints/logbook progress so they do not become arbitrary wiki bait.

## 9. Event-based unlock engine

Do not hardcode each secret into battle code.

Battle emits normalized events:
- `damage`
- `downed`
- `move`
- `displace`
- `status`
- `intercept`
- `reaction`
- `tactic`
- `objective_progress`
- `cast_started/resolved`
- `engagement_entered/left`

Campaign statistics consume events into counters and sequence detectors.

Example data concept:

```json
{
  "id": "spore_cascade",
  "members": ["ziggy", "momo", "luma"],
  "unlock": {
    "sequence": ["slow", "forced_move", "fall_damage"],
    "same_target": true,
    "max_ticks": 30,
    "count": 3
  }
}
```

The battle engine should not know why this unlock matters.

## 10. Prepared vs known tactics

A pair may know more tactics than can be taken into one mission.

Target structure:
- known tactics: progression collection;
- prepared tactics: mission loadout;
- automatic fundamentals: small generic set.

This prevents a large roster from creating hundreds of simultaneous passive checks.

Example:
Ziggy + Momo know:
- Intercept Bond;
- Launch;
- Prism Break;
- Last Stand.

Only two are prepared for the mission.

## 11. Formation tactics

Formation is a first-class Team dimension.

### Shield Wall
Adjacent defenders:
- resist push;
- can share Intercept coverage;
- control a line.

### Phalanx
Polearms:
- second-rank reach;
- engagement range 2;
- lane denial.

### Pincer
Two allies on opposing sides:
- tactical follow-up/control.

### Crossfire
Separated ranged units with shared LOS:
- coordinated ranged pressure.

### Escort Diamond
Protectors form a moving control shell around a carrier.

These formations should arise from spatial rules, not rigid "formation mode" animations.

## 12. Readability

The player must see:
- engagement zones;
- prepared reaction zones;
- who is threatening a movement path;
- available team tactics before committing;
- which partner will spend a charge/CT;
- whether a tactic is automatic or manually activated;
- why a tactic is unavailable.

Forecast should include reaction/tactic branches separately from direct damage.

## 13. AI requirements

AI must use the same public queries:
- `engaged_by(unit)`;
- reaction threat query;
- available team tactics;
- tactic forecast;
- path danger.

Future coordinated AI should understand:
- setting up a pincer;
- protecting artillery;
- entering/leaving engagement;
- baiting Vigilance;
- using Guard to control an objective;
- preserving a bondmate or combo partner.

## 14. First implementation slice

Combat 1.1 should implement only the framework necessary to prove the design:

- engagement/control-zone queries;
- ranged basic-attack penalty while engaged;
- `prepare: overwatch` command;
- deterministic single-charge Overwatch triggered by movement;
- reaction expiration at next activation;
- reaction threat query;
- pincer/follow-up Team Tactic query + bounded execution;
- normalized tactic/reaction/engagement events;
- tests for replay/rollback determinism;
- design docs for future bond/unlock persistence.

Do **not** implement the entire bond progression tree in the first slice.

## 15. Research anchors

### XCOM 2: War of the Chosen
Soldier Bonds explicitly convert repeated joint deployment/compatibility into tactical benefits. The official manual documents Teamwork, Spotter, Stand By Me, Advanced Teamwork and Dual Strike.

https://assets.2k.com/1a6ngf98576c/6LIsXornIgRpO5WnGoU1oS/d99b534548498ac045f80e5888d2c3f3/XCOM2_WOTC_ONLINE_MANUAL_SHEET_ENG.pdf

Firaxis also described building these systems by first implementing a small core and adding complexity only after it proved fun:

https://xcom.com/news/breathing-more-layers-and-life-into-xcom-2-war-of-the-chosen/amp

### Chrono Trigger
Double/Triple Techs are distinct collaborative techniques requiring the relevant characters/skills, providing a useful precedent for explicit combo actions rather than passive adjacency bonuses.

https://shmuplations.com/chronotrigger2/

### Delayed/reaction actions
Attacks of opportunity and reaction fire can be understood as reserved future actions that increase the tactical value of movement and action economy:

https://www.gamedeveloper.com/design/12-ways-to-improve-turn-based-rpg-combat-systems


## 16. Melee control ecosystem — next experiments

Engagement becomes interesting only if it creates a network of threats and counters.

### Disengage — IMPLEMENTED
Spend Act while engaged to mark the unit for a safe withdrawal. The following Move does not trigger Opportunity.

Design role:
- clear counterplay to melee lock;
- converts enemy control into an action-economy cost rather than hard immobilization;
- preserves Move/Act order freedom.

### Charge — IMPLEMENTED PROTOTYPE
A melee unit that enters engagement after moving a minimum straight-line distance may use a charge attack.

Potential parameters:
- minimum approach distance;
- straight-line or limited-turn requirement;
- bonus push rather than pure damage;
- extra CT cost;
- vulnerability to Guard/Brace/polearm control.

Preferred identity: **position conversion**, not a generic damage multiplier.

Current prototype: `{"kind":"charge","cell":[x,y]}` targets an aligned enemy. The engine
requires at least two straight movement cells, automatically stops at melee/reach distance,
spends both Move and Act plus 20 CT, resolves the normal basic attack and, on a direct hit,
attempts a one-cell push. Ordinary movement reactions/hazards still apply during the approach;
Brace can absorb the push and an interrupted approach does not roll back the reactions already
resolved.

### Brace — IMPLEMENTED
Spend Act to anchor against forced movement/charge until next activation or first trigger.

Current prototype: spend Act to prepare one Brace charge; the first Push/Pull absorbs up to 2 forced-movement cells and applies the prepared-reaction CT tax. Future extensions may reduce fall risk and stop Charge.

### Pursuit — IMPLEMENTED PROTOTYPE
A reaction that follows an enemy leaving engagement instead of immediately dealing damage.

Why it is interesting:
- maintains pressure;
- differs from Opportunity;
- can expose the pursuing unit;
- interacts with traps, Guard and objective zones.

Current prototype: a Pursuit reaction may follow once per enemy Move into the vacated adjacent
cell, including after Disengage. It uses Brave as its trigger chance, costs 20 CT, obeys height
and blocking rules, and is exposed by `movement_threats()`. It does not deal free damage:
its value is preserving spatial pressure.

### Challenge / Mark
An engaged defender marks one or more targets.

If a marked target attacks someone else, the defender gains a response:
- step;
- strike;
- CT gain;
- Intercept window.

Avoid traditional MMO-style compulsory taunt unless a class fantasy explicitly requires it.

### Breakthrough
Heavy melee ability that attempts to cross or displace an engagement line.

Counters:
- Brace;
- polearm Guard;
- Shield Wall.

This creates a tactical rock-paper-scissors around chokepoints without hard unit classes.

## 17. Weapon-space identities

Weapons should define geometry and timing, not only damage.

### Dagger
- engagement 1;
- weak frontal control;
- excellent flank/rear follow-up;
- low CT reaction cost;
- strong pursuit/disengage tools.

### Sword
- engagement 1;
- balanced Guard/Counter;
- flexible facing;
- reliable pincer contributor.

### Axe / heavy weapon
- engagement 1;
- high push/guard-break potential;
- expensive CT;
- weaker reaction economy.

### Spear / polearm
- engagement 2;
- lane control;
- strong Guard vs Charge;
- potential dead/weak zone at adjacency depending on playtest.

### Shield
Shield is better modeled as a control/protection tool than a passive armor number:
- Intercept;
- Brace;
- Shield Wall;
- directional cover;
- push resistance.

### Bow
- map-scale LOS reach;
- optimal-range window;
- falloff;
- weak under engagement;
- good high-ground/crossfire identity.

### Crossbow / firearm
- map-scale LOS reach;
- stronger long-range accuracy;
- reload/setup/CT cost;
- powerful Overwatch identity.

### Focus / spellcasting implement
- range constrained more by cast time, LOS, resource and interruption than by a small hard radius.

## 18. Team Tactics 2 candidates

### Crossfire — IMPLEMENTED PROTOTYPE
Two ranged allies have LOS to the same target from sufficiently distinct vectors. The current version requires both members to know/prepare Crossfire, both to be unengaged, the partner to have CT reserve, and rejects same-ray firing positions.

Activation should require more than adjacency:
- angular separation;
- both not engaged;
- partner CT reserve;
- prepared/known tactic.

Possible effect:
- partner follow-up;
- suppress/mark;
- reduce cover/evasion from facing.

### Launch / Relay
One ally converts its action or CT into another ally's position.

Variants:
- throw/boost;
- pull ally out of danger;
- swap;
- hand-off objective;
- relay movement.

Critical guardrail: must not invalidate authored topology. Height, mass, objective-carrier and cooldown restrictions should be available.

### Intercept Bond
A prepared tactic tied to a specific bondmate or protected zone.

Possible resolution:
1. redirect eligible hit to protector;
2. move protector one cell if legal;
3. consume bond/reaction charge;
4. optionally enable counter.

### Rescue Chain
A support character moves/heals/cleanses an ally and another linked character gains a discounted reposition.

### Spell Weave
Two casters with compatible pending spells can combine them.

Examples:
- fire + spores -> explosive/burning spore field;
- wind + fire -> directional flame expansion;
- water + lightning -> conductive zone;
- slow + delayed strike -> timing combo.

The combo should alter geometry/timing/status, not just add both damage values.

### Encirclement — IMPLEMENTED PROTOTYPE
Three prepared melee bondmates occupy three distinct cardinal axes around one target. A normal
basic attack can then trigger two bounded follow-ups; both partners spend 20 CT and each
follow-up deals one third of its normal basic damage. The rule is explicit and forecastable,
so the trio bonus comes from formation + reserve timing rather than a passive aura.

### Temporal Relay
A character spends CT to advance or synchronize a partner's next activation/cast.

This should be heavily bounded because CT manipulation can dominate the entire game.

## 19. Bond progression philosophy

Do not use a single friendship XP bar as the only unlock gate.

A bond has several dimensions that can be derived from play:
- missions together;
- protection events;
- assists;
- shared boss kills;
- terrain combos;
- rescue/revive events;
- objective hand-offs;
- synchronized casts;
- low-HP victories;
- repeated formation usage.

A tactic unlock can combine dimensions.

Example:
- **Guardian Pair**: 3 Intercepts + finish an escort mission together.
- **Hunter Pair**: 5 shared elite kills + 3 pincers.
- **Spore Cascade**: execute status → displacement → terrain damage sequence 3 times.
- **Last Stand**: win a mission with both bondmates below 20% HP.
- **Secret Trio**: a specific three-unit sequence inside one CT window.

The system should expose **hints after partial progress** for hidden unlocks:
- Unknown condition: no hint;
- discovered clue: thematic hint;
- near completion: partial measurable clue;
- unlocked: exact historical condition shown in codex.

This keeps discovery without turning the design into mandatory external-wiki archaeology.

## 20. Priority order after Combat 1.1

1. Make CI/replay/forecast proof solid.
2. Threat/path preview for engagement + prepared reactions.
3. Disengage balance and Charge/Brace prototype.
4. Intercept as first protection mechanic.
5. Crossfire as first ranged Team Tactic.
6. Event-normalization layer for bond progression.
7. Pair/trio persistence + known/prepared tactic loadout.
8. Mission unlock rules.
9. Hidden condition evaluators.
10. Formation experiments: Shield Wall / Phalanx / Escort Diamond.
11. AI influence maps and coordinated setup scoring.
12. Telemetry: engagement duration, reaction value, tactic frequency and opportunity cost.

Influence maps are a strong candidate for step 11 because Game AI Pro documents their use for tank positioning between threats and vulnerable allies, threat estimation, safe positions, AoE clustering and emergent small-group coordination:

https://www.gameaipro.com/GameAIPro2/GameAIPro2_Chapter30_Modular_Tactical_Influence_Maps.pdf


## 21. Current declarative unlock examples

### Repeated targeted kills + mission

```json
{
  "id": "pincer",
  "members": ["ziggy", "momo"],
  "unlock": {
    "all": [
      {"stat": "shared_kill:grincheux", "gte": 3},
      {"completed_mission": "garden"}
    ]
  }
}
```

### Secret same-target sequence

```json
{
  "id": "pincer",
  "members": ["ziggy", "momo"],
  "unlock": {
    "sequence": [
      {"kind": "status", "status": "slow"},
      {"kind": "displace", "mode": "push"},
      {"kind": "damage"}
    ],
    "same_target": true,
    "max_ticks": 10,
    "require_sources": "all_members"
  }
}
```

### Bond statistics currently recorded

- `missions_together`
- `shared_kills`
- `shared_kill:<target-id>`
- `tactic:<tactic-id>`
- `intercepts`
- `intercepts_for:<protected-id>`
- `rescues`

This vocabulary should grow from normalized events, not pair-specific condition code.

## 22. Implemented Combat 1.1 command vocabulary

```json
{"kind": "prepare", "mode": "overwatch"}
{"kind": "prepare", "mode": "guard"}
{"kind": "prepare", "mode": "brace"}
{"kind": "prepare", "mode": "intercept", "target": "ziggy"}
{"kind": "charge", "cell": [x, y]}
{"kind": "disengage"}
```

Prepared reactions are anchored: moving cancels the preparation. They also disappear on the preparing unit's next activation, death, or incapacitating status where applicable.


## 23. Tactical Bonds 2 codex contract

The campaign exposes a pure `tactic_codex()` view. Each unlock reports `hidden`,
`clue`, `near` or `unlocked`, a normalized progress value, and an optional authored
hint for that reveal stage. This is UI-agnostic so the future editor/player surface can
display discovery without duplicating progression rules.

Group keys remain sorted and backwards-compatible with pair saves:
`momo|ziggy` stays valid, while trio state uses e.g. `luma|momo|ziggy`.
