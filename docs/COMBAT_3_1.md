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

- `squad:pikeman`: when adjacent to a spear comrade, spends Act to join
  Phalanx. Once the formation is operational and an enemy approaches, uses
  `phalanx_hold` to defend the corridor.
- `squad:vanguard`: takes existing protector positioning, or forms a
  Shield Wall alongside a second vanguard.
- `squad:officer`: uses a real Escort formation to protect a nearby medic.
- `squad:medic`: heals using ordinary skill forecast, otherwise retreats
  from imminent melee threats along a legal low-risk path.
- `squad:archer`: uses the existing tactical ranged handling and
  disengagement logic; no unconditional free shots or buffs.

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
