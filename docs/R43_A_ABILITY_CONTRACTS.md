# R43.A — Ability/Effect Contracts & CT Bridge

**Status:** implementation branch, not release-certified. This document covers
the first R43 code increment. R43.B (Qt Studio/Player) and R43.C (cross-mode
vertical slice + GPU/clean-machine gate) are **not delivered** by this change.

## Source of truth / compatibility

- Versioned authoring data resides in `GameProject.extensions["org.drawtemp.abilities"]`
  under the existing R24 envelope `{"schema_version":1,"data":...,"references":[]}`.
- The `data` schema is `{"version":1,"abilities":[...]}` (maximum 32).
  Individual abilities have `schema_version=1` and strict fields.
- Legacy manifests without the extension are read as an empty catalogue. No
  implicit write, migration, or GameProject version bump occurs.
- A TACTICAL_CT ability is lowered to the **existing**
  `Content.skills` /`sporebound.model.Skill` representation, using the
  existing native `Effect` and `Battle` engine. This is a derived record,
  not an independent combat registry. Other content, skills and CT rules are
  unchanged unless explicitly edited.
- Edits use `preview_ability(AuthoringSession, ability)`: one atomic
  Content+GameProject preview/apply, with original revision guards,
  undo/redo/save. If the native skill ID is already owned or diverged from
  the previously generated representation, editing fails rather than
  overwriting native data.

## Ability fields

- `id`: lowercase ASCII identifier; `name`: display label.
- `profiles`: unique `TACTICAL_CT`, `ACTION_REALTIME`, `RPG_TURN`.
  Absence of a profile means **unsupported**, never fallback.
- `cost`: `resource` (`mp` or `stamina`), `amount` (0..100);
  CT supports only `mp`.
- `target`: `team` (native skill target), `shape` (single/diamond/cross/
  square), `min_range`, `range`, `radius`. These declarative fields are
  not a replacement for the viewport or its picking logic.
- `timing`: one entry per profile, with `windup` and `cooldown`.
  Native CT has `cast_ticks` but no cooldown; nonzero CT cooldown is
  rejected rather than silently dropped.
- `effects`: 1..8 **ordered** native allowlisted effects:
  damage, heal, status, cleanse, mp. Each declares a typed `formula`,
  `element`, `scope`, `status` and `duration`. Native statuses must
  exist in the default rules registry.

### Formula contract

No Python expressions, imports, callbacks or AST evaluation. Typed nodes:
`constant`, `stat` (attack/magic/defense/resistance), `add`,
`subtract`, `percent`. Maximum 31 nodes and nesting depth 5, portable
integer-only inputs, bounded intermediate values, nonnegative final
power (0..10,000). Percentage rounding uses Python integer floor division,
including negative intermediate values. This must remain stable for replays.
Canonical SHA-256 hash is taken over the validated, sorted JSON document.

**CT v1 limitation:** only constant effect formulas compile to the
existing Skill schema. Dynamic formulas in CT fail closed until the native
Battle formula adapter is implemented and replay-tested. Other modes provide
validated, deterministic `resolve_ability` plans; this PR does not yet
execute those plans in `ActionRuntime` or an RPG_TURN runtime. No cooldowns,
target selection, interrupts, status stacking, RNG or FX are invented
at this layer: these remain native runtime responsibilities / later R43 lots.

## Headless examples

```python
from drawtemp.sdk.ability_contracts import (
    preview_ability, compile_ct_skill, resolve_ability,
)

# ability is a validated R43 JSON dict (see test_drawtemp_r43_ability_contracts.py).
plan = preview_ability(session, ability)
# Inspect without changing authored documents.
session.apply(plan)  # One canonical transaction; undo/redo handled by session.
native = compile_ct_skill(ability)  # Only the CT-compatible subset.
preview = resolve_ability(ability, mode="ACTION_REALTIME", stats={
    "attack": 9, "magic": 12, "defense": 3, "resistance": 2,
})
```

## Verification / gates still open

Headless regression module:
`python -m unittest tests_standalone.test_drawtemp_r43_ability_contracts -v`

Also run the existing Jeanne/CT, R24 authoring and action-runtime
suites; report their actual results against the final merge SHA. The suite
checks strict schema rejection, legacy no-write, native collisions,
atomic preview/undo/redo, deterministic formulas, CT compilation and
mode-negotiation failure cases.

**R43 is NO-GO** until R43.B delivers real Qt ability editing, Player
adapters and view/target parity, and R43.C proves the four-arts slice,
replay/save compatibility, deterministic gameplay at 30/60/120 render FPS,
and hardware/tri-OS Player certification. Documentation alone is not evidence.
