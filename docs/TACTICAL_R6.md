# R6 — Tactical Intelligence and Objectives (incremental integration)

R6 extends the existing deterministic tactical rules, `coordinated_ai`,
`formations3`, `bosses3`, `tactical_intents`, `Campaign.prepare`
and `Battle.execute`. It does **not** introduce another simulation engine,
AI damage formula, persistence format or new default-rules manifest.

## Delivered in this PR

| Workstream | Integration | Regression evidence |
| --- | --- | --- |
| R6.1 — Tactical Intents 2.0 | `tactical_snapshot()["enemy_plan"]` contains the *currently active* enemy's chosen command, forecast and relevant terrain/path threats, labelled `conditional`; no invented off-turn choice | Snapshot equality / battle digest test |
| R6.2 — Coordinated AI 2.0 | Existing medic/protector/focus/role behavior; objective contest now recognizes capture/escort/retreat; `squad_coordination` adds measurable frontline/medic/goal/formation state | Capture-vs-elimination AI choice |
| R6.3 — Formation Intelligence | Existing real Phalanx, Shield Wall, Escort damage/reaction commands; active formation diagnostics expose their verified state | Unit chooses Phalanx only when a spear partner is nearby |
| R6.4 — Advanced Objectives | Five additional opt-in victory conditions: capture, escort, defend, sabotage, retreat; Studio objective selector and validation | End-to-end capture and sabotage victory/replay, invalid mission rejection |
| R6.5 — Tactical Terrain & Floors | Active plan exposes height/cover/hazards/path risk. Coordinated ground archers may now take safe, reachable high-cover firing tiles; ground-only squad heal/protection/focus filters allies by floor; upper-floor actors delegate to existing layered AI | Deterministic legal move, cross-floor heal exclusion and parity with layered planner |
| R6.6 — Elite & Boss AI | New **opt-in** `adaptive_boss` behavior uses the real pathfinder/charge options to choose safer footprint-wide moves on dangerous terrain, preserve existing phase-one Guard, and show exact conditional charge/attack path; authored pending reinforcements are `possible`, queued waves are `queued` | `test_elite_boss_r6.py`: blocked/hazard terrain, multi-cell movement, phase one, charge/replay and pending-wave telegraph |
| R6.7 — Jobs & Builds UX | `party_build_preview` invokes `Campaign.prepare` on a deep copy to show effective equipment, talents, jobs, skills, team tactics and combat stats without spending JP | Build preview checks calculated stats and no campaign mutation |

## Exact victory conditions

- **capture**: *all* goal cells are simultaneously occupied by living players
  on the ground floor, with no living enemy in those cells.
- **escort**: the designated living **player** `protected_id` reaches any
  goal cell on the ground floor. If the protected character dies, standard
  `Battle._outcome` declares defeat.
- **defend**: the protected player survives through `target_ticks`. No
  arbitrary enemy-elimination requirement is added.
- **sabotage**: all authored enemy-controlled `defense` objects are disabled
  using the existing `interact` / siege rules. Requires at least one such
  object.
- **retreat**: all currently surviving player units reach the set of goal
  cells on the ground floor. Downed units are not required to occupy a cell;
  campaign consequences of casualties remain elsewhere.

Validation is done against existing `Mission.goal`,
`Mission.protected_id` and `Mission.objects`. No JSON version bump or new
mission fields are needed. Mission authoring composes the new objective rules **only** when the mission
uses an R6 objective. Other Tactical RPG 3.0 missions retain their prior
manifest; new R6 recordings require `tactical_r6_rules()` or the exact
`authored_rules_for_document` selection on replay.

## Contracts / known boundaries

1. A live enemy plan is **not** an unconditional promise: the player may
   interrupt, block, damage or alter the board. Inactive enemies get existing
   *possible/armed/scheduled* overlays only, not fabricated future commands.
2. `squad_coordination` reports comparable observed facts, not invented
   multi-turn team plans. Actual coordinated choices still use only legal
   `Battle.execute` commands and existing RNG/forecast calculations.
3. Objective selection is available in Studio, but goal-cell placement,
   protected-unit selection and defense-object editing still use their
   existing authoring surfaces. This PR does not implement an entirely new
   graphical objective editor.
4. R6.5 handles local terrain choices only: it is not long-horizon A*. R6.6
   has conservative 2D boss positioning and never invents cross-floor
   boss charges. Full multilevel boss planning and cooperation with reinforcements
   after spawn remain follow-up work.
5. R6.7 exposes a pure **preparation view model**; integrating dedicated
   party loadout controls in the final Player flow remains follow-up work.
6. The 15–30 minute standard battle duration is a **playtest design target**,
   not something that simulated CT tick counts can certify.

## Local gate

```bash
python -m unittest -v tests_standalone.test_tactical_r6
python -m unittest -v tests_standalone.test_tactical_rpg3
python -m unittest -v tests_standalone.test_tactical_ui
python -m unittest -v tests_standalone.test_tactical_levels_3720c
```

Acceptance requires actual command execution, complete replay equality,
unchanged default manifest, no campaign mutation by read-only previews and
different coordinated AI choices on different mission objectives.


## R6.6 — Elite & Boss AI (opt-in)

Set `Unit.behavior = "adaptive_boss"` in a mission authored with
`authored_rules_for_document()` or create a Battle using
`tactical_r6_rules()`. `phase_boss` remains unchanged for old advanced
replays; the new behavior gets its own versioned manifest entry `6.6`.

In phase 1, this commander uses the old guard/defend rule. At phase 2 and
above, it considers legal charges, then safe reachable positions around
walls, hazards, cover and elevation, evaluating **all cells** of a multicell
footprint. It issues only `move`, `charge`, `act` etc. through the
existing Battle executor; there is no hidden attack, damage roll or state.

Player/Studio can use `boss_r6_telegraph(battle, boss_id)` or the
`bosses` section of `tactical_snapshot(battle)`:

- `command`, `path`, `threat_cells` and `destination_cells` are populated
  only for the active boss's current decision, with **conditional** certainty.
- Pending `hp_below` reinforcement scripts are labelled **possible** and
  show their authored threshold and wave size.
- Already pending `EncounterDirector` waves are **queued** facts.
- A cast already started is **scheduled**; the forecast never promises a
  future AI action on another unit's turn.

No new save format or boss-script action was introduced. Phase events,
spawns, waves and their expiry remain in the existing trigger dispatcher.

```bash
python -m unittest -v tests_standalone.test_elite_boss_r6
```
