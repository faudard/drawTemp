# R1.9 — Visual authoring acceptance

This gate certifies a real Tk Studio interaction path, not JSON-pane editing.
It extends the R1.8 GUI transaction test with direct map/editor actions:

1. **Drag** an actual multicell bridge (mouse down, B1-Motion, mouse up).
2. **Inspect an actor** through the existing entity Toplevel and modify its name.
3. **Inspect a lever**, select a different target door using the validated combobox.
4. Select that door **on the canvas**, open **Créer événement lié à la porte**,
   configure the hazard tile, then click **Créer et simuler** in the existing
   Entity & Event Studio.
5. Assert the real authored tactical trigger and the companion cinematic
   stored in the canonical `GameProject`.
6. Undo just the event: both the trigger and cinematic must be gone together.
   Undo the remaining gestures, redo all, save both documents and boot the
   mission through `GameSession` (Player's canonical entry point).

Run with the existing CI editor Xvfb environment:

```sh
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest -v \
  tests_standalone.test_editor_r1_visual_gui
```

The gate is implemented in `tests_standalone/test_editor_r1_visual_gui.py`
and is an explicit step in `.github/workflows/standalone.yml`.

**Scope:** real 2D drag/inspector/event action/history; no schema change,
no alternative engine/document layer, no Tk dependency in commands.
This does **not** certify the complete isometric pointer-occlusion, keyboard,
RTL, multilevel, or high-DPI interaction matrices. They require separate gates.

Stack: #164 (merged) → #169 → #174 → this PR.
