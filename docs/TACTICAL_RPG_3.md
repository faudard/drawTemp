# Tactical RPG 3.0 (opt-in, headless)

This feature set extends the 2.4 session/persistence foundation without modifying
`default_rules()`. It does **not** introduce another game engine, renderer or save
format. For old campaigns and replays, keep using the default ruleset.

## Integrating the 2.7 rules

```python
from sporebound.tactical_rpg3 import tactical_rpg_rules
from sporebound.engine import Battle

rules = tactical_rpg_rules()
battle = Battle(content, "mission_id", seed=42, rules=rules)
battle.execute({"kind": "formation", "mode": "shield_wall"})
recording = battle.recording()
restored = Battle.replay(recording, rules=tactical_rpg_rules())
assert restored.digest() == battle.digest()
```

The opt-in ruleset adds one behavior, one command, two team tactics, one boss
trigger action, and two formula versions. Existing commands retain their atomic
rollback. Always pass the same ruleset on replay, import and mission preparation.
The 2.7 gameplay modules have no Tk, pygame or PySide dependency.

### 2.7.1 — Coordinated AI

Set `Unit.behavior = "coordinated"` to opt in. `Unit.tags` can include
`medic` (prioritizes legal restorative actions) and `protector` (tries to
stand next to an endangered medic, considering path costs and threats).
Otherwise the existing tactical/siege AI takes over. This is a bounded
deterministic per-activation planner, **not** a multi-turn search.

### 2.7.2 — Formations

The player and AI can submit a standard atomic command while the unit is
active and still has its action:

```python
battle.execute({"kind": "formation", "mode": "shield_wall"})
battle.execute({"kind": "end"})
# Other modes: "phalanx", "escort" (requires "target": ally ID), "none"
```

A unit can keep one formation. `shield_wall` reduces nonmagical damage while
two marked allies are adjacent. `phalanx` increases spear basic attack damage
while adjacent to another spear ally in phalanx. `escort` reduces nonmagical
damage and hit probability for its assigned adjacent ally.

`formation_preview(battle, unit_id)` is side-effect free and can power
Studio/player previews. Formations persist as `Unit.tags`; the formation
command consumes the acting unit's Act but not Move. All costs and effects use
the normal `Battle.execute`, damage and hit chance contracts.

Once two spearmen are in Phalanx, one of them can prepare `phalanx_hold`
on a later activation. Moving enemies entering the spear attack lane then
trigger the existing once-only prepared attack and pay the normal CT tax.
`formation_control_map(battle, team)` exposes sorted lane cells and whether
the associated reaction is armed. It is pure and safe to call from an enemy
intent forecast or graphical threat overlay. If the spearmen separate, the
formation no longer projects a lane; no hidden persistent aura is applied.

### 2.7.3 — Builds / talent trees

Optionally extend a job with a declarative talent map; legacy job definitions
are unchanged:

```json
{
  "jobs": {
    "brave": {
      "talents": {
        "shield_training": {
          "jp": 1,
          "bonuses": {"defense": 3}
        },
        "banner_bearer": {
          "jp": 2,
          "requires": ["shield_training"],
          "exclusive": "specialization",
          "skills": ["morale"]
        }
      }
    }
  }
}
```

The example requires a `morale` skill defined in content. JP budget is
`job_xp // 50`. Learned talents and spent JP are stored in the existing
`HeroProgress`/Campaign v1 slots, with default empty fields for old saves.
Call `Campaign.learn_talent(content, hero_id, job_id, talent_id)`, then
`Campaign.prepare(..., ruleset=rules)`. No implicit refunds; respec and a
Studio point-and-click authoring UI are future work.

### 2.7.4 — Proximity synergies

Units can unlock and prepare `chain_strike` (duo, 25 partner CT) and
`trio_burst` (trio, 30 CT per partner) via the **existing** bond codex and
`Content.tactic_unlocks`. Only prepared units receive the tactics in battle.
The conventional `Battle.available_team_tactics`, forecast, resolver and
replay handle the damage. Partner eligibility requires shared tactical
range/proximity and reaction availability. The existing `pincer`,
`crossfire` and `encirclement` remain intact.

### 2.7.5 — Multi-cell, multi-phase bosses

Use an existing `hp_below` trigger and a new declarative `boss_phase` action.
Other actions on the trigger can enqueue siege waves.

```json
{
  "id": "warden_giant",
  "condition": "hp_below",
  "unit": "warden",
  "percent": 60,
  "actions": [
    {
      "kind": "boss_phase",
      "unit": "warden",
      "phase": 2,
      "form": "giant",
      "footprint": [2, 2],
      "bonuses": {"attack": 4, "defense": 2}
    },
    {"kind": "message", "text": "The throne guardian awakens"}
  ]
}
```

Phase transitions fire once via the existing `fired` trigger journal. Invalid
growth into walls or occupied cells is rejected atomically. Form is metadata
for the renderer, not a sprite loader. `boss_preview()` exposes the current
form and upcoming thresholds.

The optional `Unit.behavior = "phase_boss"` selects a defensive Guard policy
at close range during phase one, legal long-lane Charge attempts in later phases,
and the existing tactical/siege AI otherwise. No battle-state mutation occurs
in the choice callback. `examples/tactical_rpg3_castle.py` equips the castellan
with this behavior while leaving the original siege fixtures unchanged.

### 2.7.6 — Balance gates

```python
from sporebound.balance3 import evaluate, verify_budgets

report = evaluate(content, "mission_id", seeds=[1, 7, 42, 99],
                  max_commands=500, rules=tactical_rpg_rules())
verify_budgets(report, max_p95_commands=500, allow_limits=False)
```

Reports contain per-seed outcomes, win rate, allied downed mean, and
nearest-rank p50/p95/p99 for command count and ticks. Re-running identical
seeds and content must produce identical reports. `allow_limits=False`
rejects encounters that fail to terminate within the cap. These are **gameplay
budgets**, not wall-clock CPU performance metrics.

## Gate / integration checklist

- Old `default_rules` manifest and v1/2/3 Battle replay unaffected.
- Campaign v1 slots with no JP/talent keys load unchanged.
- New commands fail atomically and replay using `tactical_rpg_rules()`.
- Save/replay preserves formation choice, phase transitions and CT combos.
- Tests exercise a multi-cell boss and seeded difficulty reports.
- The 2.5 Studio and 2.6 player must consume these APIs; adding UI logic
  that duplicates the headless formulas is expressly disallowed.

### Boundaries

The new formation and boss actions are opt-in. The 2.7 policy is a gameplay
foundation; final unit balance, long-campaign benchmarks, telegraph UI,
class-tree editing and an authorable castle vertical slice still require
end-to-end integration.
