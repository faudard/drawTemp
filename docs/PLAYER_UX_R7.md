# Player UX R7.1–R7.6 — interface autonome

This integration extends the existing `PlayerApplication`, `PlayerController`,
`BattleFrame`, `IsoBattleCanvas`, and `GameSession`. It deliberately does not
introduce a second Player, a parallel tactical ruleset, or another save format.

## Delivered scope

| Lot | Player behavior | Verification |
| --- | --- | --- |
| R7.1 | Title / slots / campaign / roster / deployment / battle / new **results** screen / campaign return; all game mutations go through `PlayerController` | Standalone startup and resume smoke; results screen requires a finalized encounter |
| R7.2 | Read-only objective, actor HP/MP, active actor, CT ETA, authoritative damage forecast and event journal | Headless deterministic projection + GUI smoke |
| R7.3 | Selection via keyboard arrows, Ctrl+arrows pan, mouse pan, anchored zoom and exact 24/54/96 presets in 2D and isometric views; existing floor-aware hit test and multicell actor footprint display | Camera anchor + multicell + zoom tests |
| R7.4 | Selection summary of reachable cells and known threats, categorized by certainty; accurate forecasts only when the engine supplies them | Digest invariance and snapshot tests |
| R7.5 | UI presentation revision prevents callbacks from earlier cinematics from resuming an interrupted screen; transitions cancel scheduled frame/typewriter/world tasks | Revision gate tests |
| R7.6 | Visible Canvas focus, scoped, remappable collision-checked keybindings, higher-contrast palette, 100/125/150% text sizes, compact HUD | Keyboard mapping and Tk smoke |

Accessibility preferences and keybindings are held **in process**, not stored in the
versioned GameSession. Comboboxes and other input widgets retain their native
keyboard handling. The title and campaign flow also remain available when
optional imagery, sound, or cinematics are missing.

## Tactical feedback contract

HUD entries come exclusively from `battle_frame` / `tactical_intents`.
A red hazardous tile represents known terrain danger; a cast is scheduled;
a prepared reaction is armed; an enemy charge is merely possible.
CT times are estimates and may change if speed or status changes.
The Player does **not** fabricate LOS, damage probabilities, movement costs or
future AI decisions. If the engine cannot calculate a forecast, none is shown.

## CI acceptance evidence

The `standalone.yml` workflow runs the headless `test_player_ux_r7`
cases on Linux/macOS/Windows Python 3.10/3.12/3.14. It now **also** runs
`test_player_ux_r7_gui` explicitly under Xvfb on Linux instead of relying
on `unittest discover`, where display-dependent cases would be skipped.
The GUI smoke exercises 2D/isometric zoom, focus-bound remapped shortcuts,
contrast, HUD density, results rendering and transition invalidation.
The terminal result in that test is an **in-memory UI fixture only** and
must never be saved; separate GameSession tests exercise replay-valid
campaign progression and persistence.

## Verification commands

```sh
python -m unittest tests_standalone.test_player_ux_r7 -v
python -m unittest tests_standalone.test_presentation tests_standalone.test_player_controller -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_player_ux_r7_gui tests_standalone.test_player_26_gui -v
python -m sporebound player --content sporebound/content/core.json
```

Manual gate: launch outside Studio; select a save slot; start a campaign and
mission; deploy; select a footprint tile; inspect reachable cells and
contrasted threats; switch between 2D/isometric; pan and zoom at all three
presets; configure nonconflicting shortcuts; finish a battle; view results;
return to campaign, save and resume. Repeat with a tactical cinematic interrupted
by navigating to another screen.

This PR supplies the architecture and focused checks; completion of the manual
visual/accessibility matrix and all-platform CI remains required before claiming
full R7 acceptance.
