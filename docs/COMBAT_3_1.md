# Combat 3.1 — positional decisions, readable threats, squad roles

This is an **opt-in** extension to Tactical RPG 3.0. It keeps the existing
CT scheduler, movement budget, command log and deterministic replay. It does
not replace Battle or introduce a second damage/AI path.

## Directional melee pressure

In the enhanced ruleset only, a basic melee/spear/unarmed attack does:
- **Front:** existing damage;
- **Flank:** 120% damage, after existing mitigation;
- **Rear:** 140% damage, after existing mitigation.

The facing sector uses the closest occupied tile pair, including actors larger
than one tile. Forecast and actual hit use the **same** mitigation rule. The
existing direction-based evasion remains in force. The bonus is not granted to
ranged/magical attacks, and does not affect legacy default_rules() saves.

The shared `spatial3.positional_preview` can be displayed during target
selection. `tactical_ui.tactical_snapshot` also exposes it.

## Enemy telegraphs

`tactical_intents.tactical_intents(battle)` returns a pure, JSON-serializable
view of:
- **Estimated CT:** current unit and one next-ready estimate per combatant,
  assuming unchanged speed. Stop/Sleep are marked blocked.
- **Scheduled casts:** exact current target (cell/unit lock), area and ticks
  remaining. A moving unit-locked target can move the future hit area.
- **Armed reactions:** projected enemy prepared-threat cells.
- **Possible boss charges:** legal lanes *if selected now*, not a promise that
  the boss will select that action on a future activation.
- **Terrain dangers:** existing hazard tiles.

The projection never consumes RNG and does not call a speculative AI rollout.
Prepared overlays are capped at 1,024 board cells (`truncated` is explicit)
for very large maps. CanvasRenderer outlines casts in violet, armed reactions
in yellow, possible charges in orange and terrain hazards in red. Both Tk
players show a compact CT/cast/charge summary.

## Legal player actions

`tactical_actions.tactical_action_options` presents currently available
`charge`, `disengage`, `formation`, `prepare` and `relay` choices.
`tactical_command` translates a selected option into an ordinary engine
command. The target tile is still chosen on the map and Battle.execute retains
all final validation, cost, rollback and replay semantics.

## Coordinated AI roles

Add one tag to actors already using the enhanced ruleset, without inventing a
new unit/monster schema:

- `squad:pikeman`: moves to screen exposed archers, spends Act to join
  Phalanx alongside a spear comrade, and uses `phalanx_hold` to defend
  the corridor when an enemy approaches.
- `squad:vanguard`: takes existing protector positioning, or forms a
  Shield Wall alongside a second vanguard.
- `squad:officer`: uses a real Escort formation to protect a nearby medic.
- `squad:medic`: heals using ordinary skill forecast, otherwise retreats
  from imminent melee threats along a legal low-risk path.
- `squad:archer`: seeks a legal firing position behind nearby melee
  guards if it cannot currently shoot, then uses ordinary attacks,
  reactions and disengagement. No unconditional free shots or buffs.

Tags are opt-in through `authored_rules_for_document` or explicit
`tactical_rpg_rules()`. Unmarked campaigns and old replay manifests are
unchanged. Each AI choice is a normal Battle.execute action.

## Validation

```sh
python -m unittest discover -s tests_standalone -p test_combat31.py -v
python -m unittest discover -s tests_standalone -v
python -m sporebound validate
```

The targeted suite checks directional damage, large actors, forecast/replay
parity, exclusive synergies, pure CT and hazard previews, cast and prepared
overlays, legal menu actions, formation building, officer escort and medic
retreat. The standard multiplatform CI remains the acceptance gate.

## Deliberate follow-ups

- True squad-wide multi-activation planning and flanking search beyond the
  bounded per-activation role policies.
- Player hotkeys, richer directional arcs and dynamic cast marker labels.
- Adaptive shielding, line-of-sight and footprint-aware terrain control
  for siege monsters over multiple tiles.
- Encounter-level balance trials with scenario difficulty curves.

## Integrated encounter: Jeanne — courtyard breach

Use the existing castle mission pack with an extra **Jeanne** mission.
The encounter is alternate-history fiction, not a claim about the real 15th
century siege. It uses four attackers and six compact defenders; the player
must break a spear line, neutralize the archer, and deny the medic/officer pair.

The layout has a narrow central passage, cover just outside the breach, and
two opposing deployment zones. The enemy pair of pikemen can form phalanx,
the knight screens support, the archer stays behind melee guards, the medic
heals/retreats, and the officer can escort the medic and cast an observable
area spell. Every action uses the existing CT schedule and Battle.execute.

```sh
# Inspect defender roles, positions and initial CT estimates:
python -m examples.jeanne_combat31 --preview

# Generate an editor-importable JSON scenario alongside castle missions:
python -m examples.jeanne_combat31 --export jeanne_siege.json

# Exact-seed A/B against identical enemies without squad role tags:
python -m examples.jeanne_combat31 --compare

# Smaller, faster development check:
python -m examples.jeanne_combat31 --compare --max-commands 150
```

A/B reports use `compare_compositions`, the same seeded engine simulation,
the same player AI in both variants, identical map, unit stats, rosters and
ruleset; **only the enemy `squad:*` tags change**. Examine victory rate,
mean damage, downed heroes, command p95 and `formation`/prepared events.
The numbers are descriptive, not a statistical claim, and seeded automated
AI is not a substitute for a human playtest.

To calibrate the damage multipliers, choose a target difficulty from the
measured outcomes and actual manual matches. The current 120% flank and 140%
rear are provisional (not declared balanced just because CI is green).
The next gate is a decisive, readable engagement with at least two viable
player counters: flank the spearholders, or pressure the healer/officer with
ranged fire while holding the gate.
