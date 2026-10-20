# R51.B — UI & HUD Designer / Qt Quick shared preview

**Implementation PR (stacked on R51.A #397) · 20 October 2026.**
Not a certification of R51, R50, native Player exports, gamepad use, or GPU.
The R51.A branch remains the contractual base until it reaches `master`.

## Delivered increment

- Pure headless layout draft: add, edit, reorder and remove typed widget
  nodes; responsive breakpoint authoring; invalid changes fail without
  mutating the original draft. Full document v1 validation is always reused.
- Studio dialog `R51DesignerDialog`: UI-tree editor, properties inspector,
  typed text bindings, authored action selector, breakpoint controls,
  live resizeable Qt Quick preview, R1 staging/apply and Undo/Redo.
  Entry point: **Studio → Outils → UI & HUD Designer R51**.
- **One shared Qt Quick component**, `drawtemp/player/R51Layout.qml`
  plus recursive `R51Node.qml`, loaded by QQuickWidget in Studio
  and from Player Main.qml at runtime. No second QML schema,
  runtime compiler, eval, embedded scripts or gameplay registry.
- Player opt-in projection via `drawtemp/player/r51_hud.py`, consuming
  the existing `PlayerController → Simulation → GameSession → BattleFrame`
  chain. HUD_CT screens are read from the canonical GameProject extension.
  The visible authored HUD is an **additional preview panel** beside
  the legacy battle UI; replacing the battle menus is not yet complete.
- The only executed authored action in this increment is
  `combat.end_turn`: after explicit check that an actual human CT
  turn exists, it delegates to `PlayerController.command("end")`.
  Unsupported intents are disabled in QML and fail closed in Python.
- Qt labels explicitly use `Text.PlainText` for untrusted author labels;
  the inspector never interprets text as QML/HTML.
- Headless tests for draft atomicity, responsive preview, R1 history
  and Player deny-by-default; optional Qt Quick smoke for tree→inspector→
  preview→R1 preview/apply→undo/redo.

## Author workflow

1. Open an authored project in the existing R1 Studio.
2. Select **Outils → UI & HUD Designer R51**.
3. Create a new screen (HUD_CT, HUD_ACTION, MENU, DIALOGUE or INVENTORY),
   inspect its widgets, add typed controls to an existing container,
   change properties, move components or configure width breakpoints.
4. Resize the visual preview: **its values are synthetic samples**,
   never a runtime simulation, and its action buttons are disabled.
5. Click *Préparer la transaction*; only click *Appliquer* if the draft
   is valid and intended. Undo/Redo modifies the shared R1 history.
6. Save the whole project with the existing Studio save. For a real
   CT battle in the standalone Player, the opt-in HUD_CT is resolved
   against the current canonical frame and displayed via the exact
   same QML component; its only enabled command is CT end-turn.

## Deliberate limitations and gates

- GUI tree editing is not unrestricted drag/drop. The author can add,
  remove and move siblings with visible buttons; editing the exact
  gauge binding tuple, arbitrary style tokens and compound widget
  conversion need follow-up R51.B increments.
- Available focus order is validated and carried into the projection,
  but QML spatial focus and hardware gamepad mapping are **not certified**.
  Only keyboard-focusable existing Qt buttons are used.
- Menus, dialogue and inventory schemas can be authored and previewed;
  replacement of their real Player screens and input routing is not
  claimed. HUD_ACTION and advanced combat bindings require real R26
  Player acceptance tests.
- HUD_CT during deployment, enemy activation or invalid bindings
  falls back to the legacy UI without invoking an action.
- This PR does not remove the old HUD or rewire hard-coded default
  screens. An opt-in authoring extension never alters legacy UX.
- The preview example must not be represented as proof of a gameplay
  replay, Qt onscreen, gamepad input or export; R51.C still owns parity,
  accessibility, licensed assets and clean-machine tri-OS certification.

## Tests

```bash
python -m unittest -v tests_standalone.test_r51a_ui_layout tests_standalone.test_r51b_layout_designer
python -m unittest -v tests_standalone.test_r25_foundation tests_standalone.test_player_hud_layout_r710

# Optional **software offscreen smoke only** on a machine with PySide6:
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software DRAWTEMP_R51_QT_GATE=1 \
  python -m unittest -v tests_standalone.test_r51b_qt
```

**CI note**: the previous PR R51.A (#397) observed GitHub workflows
returning `failure` with zero jobs launched. No unit test, QML render,
GPU check or release may be claimed green without actual job logs.
