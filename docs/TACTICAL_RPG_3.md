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

The opt-in ruleset adds two behaviors, one formation command, a Phalanx Hold
preparation, two team tactics, one boss trigger action, and two formula versions. Existing commands retain their atomic
rollback. Always pass the same ruleset on replay, import and mission preparation.
The 2.7 gameplay modules have no Tk, pygame or PySide dependency.

### 2.7.1 — Coordinated AI

Set `Unit.behavior = "coordinated"` to opt in directly. With the
enhanced ruleset, a unit whose stored behavior is the legacy `tactical`
also uses coordinated healing/protection if the Studio-authored tags include
`medic` or `protector` (unless a patrol route is configured); untagged
actors keep the previous policy. `medic` prioritizes legal restorative
actions, while `protector` tries to stand next to an endangered medic,
considering path costs and threats.
An optional focus-fire pass ranks enemy targets by real combat forecast,
potential lethality and immediately available allied basic attacks. It may
change the target of an already-selected basic attack; it never overrides
healing, siege interactions, spells or movement. Use
`squad_focus_preview(battle)` to render the predicted target and supporting
actors without consuming RNG. Otherwise the existing tactical/siege AI takes
over. This is a bounded deterministic per-activation planner, **not** a
multi-turn search.

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
while adjacent to another spear ally in phalanx. Taking the high ground
adds a further spear bonus; a Shield Wall on terrain with cover ≥20 mitigates
more physical damage. Both use the exact same formula in forecast and attack
resolution. `escort` reduces nonmagical damage and hit probability for its
assigned adjacent ally.

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
complete Studio talent-tree editing UI are future work. The actor inspector
already exposes initial tactical roles (`medic`, `protector`) and starting
formations with validated, undoable edits. The Studio playtest automatically
selects `tactical_rpg_rules()` when any authored unit has tactical tags; old
untagged documents retain the original default rules and replay manifest.
For standalone player/campaign sessions, explicitly pass the enhanced ruleset.

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
form and upcoming thresholds. `boss_intent_preview()` returns the current
active boss's chosen command and, where applicable, its charge or skill
threat forecast; off-turn plans are intentionally not guessed.

The optional `Unit.behavior = "phase_boss"` selects a defensive Guard policy
at close range during phase one, legal long-lane Charge attempts in later phases,
and the existing tactical/siege AI otherwise. No battle-state mutation occurs
in the choice callback. `examples/tactical_rpg3_castle.py` equips the castellan
with this behavior while leaving the original siege fixtures unchanged.

### 2.7.6 — Balance gates

```python
from sporebound.balance3 import compare_compositions, evaluate, verify_budgets

report = evaluate(content, "mission_id", seeds=[1, 7, 42, 99],
                  max_commands=500, rules=tactical_rpg_rules())
verify_budgets(report, max_p95_commands=500, allow_limits=False)
```

Reports contain per-seed outcomes, win rate, allied downed mean, and
nearest-rank p50/p95/p99 for command count and ticks. Every seed also
records a deterministic battle digest, event counts, team tactic activations and
damage received by player units. Aggregated telemetry supports comparing
formation-heavy encounters with direct damage builds; the optional
`max_mean_damage_taken` CI gate guards against overtuned enemy teams.
Re-running identical seeds and content must produce identical reports.
`allow_limits=False` rejects encounters that fail to terminate within the cap.
Use `compare_compositions({"default": content_a, "elite": content_b},
"mission_id", baseline="default", seeds=[1, 7, 42, 99])` for controlled
paired-seed comparisons. The returned win-rate, damage and casualty deltas are
descriptive, not statistical significance tests.

These are **gameplay budgets**, not wall-clock CPU performance metrics.

## 2.7 — Player and visual talent integration

The Tk Player now consumes `tactical_snapshot(battle, cell)` directly.
It shows armed ally/enemy phalanx corridors on the board and a tactical
panel with forecast damage, available duo/trio synergies, formation status,
movement hazards, supported focus targets, and the **active** boss's legal
intent. Off-turn intents remain unknown rather than predicted from stale CT.
Formation choices (including escorting the ally on the selected cell) and
Phalanx Hold use normal atomic `Battle.execute` commands.

`PlayerSession.begin` selects the 2.7 rules only for authored missions
containing the appropriate behaviors/role tags/formations. Untagged legacy
missions continue to use their original default rule manifest. The Player
loads advanced content with the 2.7 validator to accept authored boss forms.

The Studio actor inspector can author initial formations, medics and protectors.
Its **Talents / classes** tab provides a dependency tree and structured
fields for JP cost, prerequisites, specialization, a stat bonus, and skill
unlocks. Updates are validated through `Content.from_dict` and committed
as a single undoable document transaction. Dangling or cyclic prerequisites
are rejected. This initial UI edits one stat bonus per talent; more advanced
multi-effect and graph-layout tools remain future authoring work.

On the campaign screen, the Player presents a talent dependency tree and
allows purchases with earned JP. `PlayerSession.learn_talent` saves the new
campaign slot before changing in-memory progression, rejects unavailable
talents and blocks mid-battle upgrades. Purchased bonuses take effect during
the next `Campaign.prepare` and survive reloads.

## Gate / integration checklist

- Old `default_rules` manifest and v1/2/3 Battle replay unaffected.
- Campaign v1 slots with no JP/talent keys load unchanged.
- New commands fail atomically and replay using `tactical_rpg_rules()`.
- Save/replay preserves formation choice, phase transitions and CT combos.
- Tests exercise a multi-cell boss and seeded difficulty reports.
- The Studio's actor/talent inspectors use validated, undoable document
  transactions; the Player consumes the same pure tactical forecasts and
  implements saved JP upgrades without duplicating combat formulas.

### Boundaries

The new formation and boss actions are opt-in. The 2.7 policy is a gameplay
foundation; final unit balance, long-campaign benchmarks, telegraph UI,
advanced multi-bonus tree layout, audio/animated telegraphs and an
authorable castle vertical slice still require end-to-end integration.
