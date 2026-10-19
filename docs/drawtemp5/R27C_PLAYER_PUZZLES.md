# R27.C — Player context actions, visual state and verified battle resume

**Status:** proposed stacked incremental PR above R27.B (#319), which is itself
stacked above R27.A (#304). **Not** a complete R27/6.3 gate or R25/R26
real-time scene-transition implementation.

## Delivered in this increment

The standalone Qt Quick Player 5.0 now has a **contextual puzzle panel** when
the active canonical battle contains R27.B key, plate or pushable-block objects,
or a gate with a key/ordered switch policy. It uses the existing R12 Simulation
and the shared R3 isometric renderer — not a second gameplay controller.

- Only nearby interactable keys, linked doors, levers, chests and pushable
  blocks are proposed to the active player. Disabled choices indicate when
  preconditions are unmet. Selected-cell controls appear first.
- Canonical gate state (collected key, switch order/progress, plate activation,
  block position, open/closed gate) is shown as **derived information** from
  `Battle.state()["objects"]`. No extra gameplay state is stored by QML.
- Pressing a contextual action sends only its **object ID** to
  `PlayerController.puzzle_action`. The Python Player recomputes the
  revision-checked authoritative preview (including push direction) and
  commits the actual engine command through `Simulation.execute`.
  Qt never supplies a forged destination, inventory flag, or gate rule.
- The same R3 object projection renders a collected key dimmed, a pressed
  plate activated, a movable block distinguishable, and puzzle doors with
  visible types. Existing legacy scene shapes remain unchanged when puzzle
  fields are absent.
- Non-puzzle tactical missions keep their legacy object-action list. Other
  siege objects remain reachable from the standard interaction panel.

## Verified-save scope

Every successful command passes through the **existing** R12 autosave
boundary. An invalid puzzle action does not advance a Simulation revision or
alter the recorded autosave. A Player manual save and autosave both contain
the canonical verified GameSession and Battle replay — including collected
keys, open doors, pushed blocks and latched plates — exactly as they existed
at the **current battle's** checkpoint. A resumed game reconstructs them
from the replay, not a new separate JSON save file.

**Important:** this does not implement carrying keys between missions,
seamless scene transfer, persistent world-wide object state, or action-mode
controls. Those depend on R25 profiles/SceneRouter and R26 runtime work.

## Test gates

```bash
python -m unittest tests_standalone.test_drawtemp5_r27c_player -v
python -m unittest tests_standalone.test_drawtemp5_r27_dungeon tests_standalone.test_drawtemp5_r27_puzzles -v
python -m unittest tests_standalone.test_drawtemp5_r12 -v
```

Actual QML smoke, Linux CI with software Qt (no hardware-GPU claim):

```bash
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software \
DRAWTEMP_R27C_QT_SMOKE=1 \
python -m unittest tests_standalone.test_drawtemp5_r27c_qt -v
```

Dedicated workflow: `.github/workflows/drawtemp-r27c.yml`
(Python 3.10/3.12 and offscreen Qt 6). Tests are **not green** until the
final head SHA has an actual passing GitHub check.

## Suggested visual acceptance sequence

1. From the R27.A Studio, create a 16x16 authored dungeon and a room whose
   locked door is `room_door`.
2. With the R27.B tools, place a linked `amber_key` next to the player's
   spawn and paint a goal inside the room.
3. Load this authored Content/Project pair in the standalone Qt Player.
   Enter the mission. The contextual panel offers **Ramasser · amber_key**
   and shows the locked gate missing its key.
4. Pick up the key. The item fades in the **shared** iso viewport and the
   puzzle state reads **Récupérée**.
5. Save to slot 1, return to title, and reload. The key remains collected
   and the same Battle recording is verified on load.
6. Advance a player turn, open `room_door` and reach the authored goal;
   check that mission progression is not silently unlocked by the puzzle HUD.

The tests cover the model/Player/Qt binding and single-battle replay aspects;
they do not constitute a manual visual or complete gameplay sign-off.

## Remaining milestones

R27 release remains **NO-GO** pending: key inventory across scenes,
persistent puzzle world checkpoints, cross-mode scene transitions/spawns,
R25/R26 engine readiness, accessible keyboard/pad actions, deterministic
multi-scene save fault-injection and clean-machine export/playable certification.
