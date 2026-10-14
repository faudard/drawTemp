# R7.9 — Action Preview 3.0

## Outcome

The Player battle screen gains an **opt-in** action preview, evaluated when
a cell is selected or hovered over. It explains *why* an action is currently
available, blocked or conditional without issuing a command.

### Ground movement
- Render the **exact path and cost** from `Battle.reachable(unit)`.
- Show crossed terrain hazards (specified damage per passage) and reactions /
  engagement hazards returned by `Battle.movement_threats`.
- Label reactions as *possible* and warn that combat can interrupt a route.
- A valid path does not guarantee arrival or outcome; teleport failure and
  scripted interruption remain runtime events.

### Attack and skills
- Query **`Battle.forecast`**, show target, damage/healing/effect values,
  chances and possible intercepting protector.
- Show a dotted line of targeting only if the **engine has validated** a
  skill that requires LOS. A skill with `los=False` does not invent or claim
  a line-of-sight check.
- Engine `RuleError` (blocked line of sight, resources, range or invalid
  targets) yields a blocked preview with the exact reason.
- A forecast is a probability/estimate, never a confirmed outcome.

### Multi-floor and objects
- Use `Battle.level_reachable` for actual stair/ladder paths and connector
  costs. Display individual floor records textually.
- Use `Battle.vertical_forecast` for shots across a floor opening.
- **Never project an upstairs target or path onto the ground plane**.
- Use `Battle.can_interact` for current object-activation eligibility.
  Interaction side effects are deliberately not simulated; `GameSession`
  remains the only execution boundary.

### UX and performance
- Opt-in **Prévision d'action** checkbox, independent from R7.8 Aide tactique.
- Preview on selection and hovered tile; mouse movement is debounced by 90 ms.
- Overlays reuse the Player's actual 2D `Camera` or isometric `IsoGeometry`
  and `IsoBattleCanvas.shift`, including the 24/54/96 px presets.
- Teal dashed movement/charge paths, amber dotted validated targeting, and
  status-colored destination outline; textual summaries remain accessible.
- No automatic gameplay action, AI operation, RNG use, save modification or
  new `Content`, `GameProject` or `GameSession` schema.

## Validation

```sh
python -m unittest tests_standalone.test_player_action_preview_r7 -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest tests_standalone.test_player_action_preview_r7_gui -v
```

CI: headless tests join the existing cross-platform/Python matrix;
the Tk test is a named Xvfb gate in `.github/workflows/standalone.yml`.

**Acceptance gate:** show the exact engine path/cost from a selected movement
destination, inspect a blocked ranged target and a validated skill forecast,
hover a multi-cell unit, switch between 2D and iso at 24/54/96 pixels, inspect
stairs/upper floors without misleading ground paths, toggle the panel off and
back on, and confirm the Battle digest is unchanged until a command is actually
executed. Run a real saved/replayed battle in both presentations.

**Out of scope:** a full pre-execution scene simulation; outcomes of scripted
object interactions; predictive enemy AI; guaranteed successful paths despite
reaction hits. Those would require verified engine projections first.
