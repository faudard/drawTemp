# R7.8 — Contextual Combat Guidance

## Player integration

The Player's existing tactical screen now exposes an **opt-in** "Aide tactique"
panel. It derives its content from the same read-only `BattleFrame` already
used by the tactical HUD, rather than maintaining a second action simulator.

The assistance changes with the actual Player phase:

- Deployment: select hero + cell, deploy, and start the battle.
- Player activation: how to use the selected action, including movement,
  attacks, floors, objects, items, formations, preparations and abilities.
- Enemy activation: run the existing AI activation command.
- Waiting for CT and finished encounters: appropriate navigation.

The panel is disabled by default, can be toggled while playing, and retains
its visible state across regular Player redraws in the same process. Changing
the selected action or floor refreshes previews without executing a command.

## Trust / correctness rules

- Movement hints only affirm cells in `BattleFrame.reachable`.
- Attack hints only acknowledge `BattleFrame.forecast`; none is invented.
- A hazard is confirmed terrain information, cast is scheduled, prepared
  reaction is armed, and charge corridor is **possible**, not guaranteed.
- Expected `RuleError` from an attempted Player action is shown in the combat
  feedback line instead of an intrusive modal; the controller still owns
  command validation, rollback and save checkpoints.
- Save or I/O failures remain surfaced by the existing error handler, not
  silently transformed into a combat rule refusal.
- No user hints generate actions, choose decisions or modify CT, AI, RNG,
  Content, GameProject, replay, GameSession or the preference sidecar.

## Verification

```sh
python -m unittest tests_standalone.test_player_guidance_r7 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_player_guidance_r7_gui -v
```

In `.github/workflows/standalone.yml`, headless tests are run through
existing unit test discovery on the OS/Python matrix; the Tk smoke is a
dedicated gate under Xvfb so tests are not silently skipped for lack of DISPLAY.

### Manual acceptance

Start a new standalone Player game without opening the Studio, enter the
deployment phase, enable the help panel, and confirm it follows selected
actions without changing the recorded Battle digest. Change between 2D and
isometric at 24 / 54 / 96 px, navigate a multicell actor, and select an
invalid target to verify that the engine refusal appears inline without losing
the current selection. Disable the help panel and resume normal play.
Replay and slot files must remain identical when simply opening the help.
