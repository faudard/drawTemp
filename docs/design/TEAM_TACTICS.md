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

### Intercept
Prepared or slotted protection rule.

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

### Hidden emergent unlock
A pattern in real battles unlocks a tactic.

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
