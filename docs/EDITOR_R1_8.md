# R1.8 — Studio Tk acceptance gate

The existing R1.5–R1.7 headless checks validate the canonical Content,
GameProject, StudioHistory and GameSession APIs. R1.8 adds a real Tk/Xvfb
integration gate with the existing editor controls.

## Reproducible GUI scenario

Start with a 20×20 mission with a multi-cell **Pont**, two doors, an actor,
a linked switch and a tactical event.

- Open the **Données JSON** authoring tab (the supported low-level editor
  path) and apply four canonical changes using **Valider et appliquer**:
  bridge relocation, actor edit, lever → other door, event condition.
- Check every intermediate snapshot while invoking **Annuler** four times.
- Check every intermediate snapshot while invoking **Rétablir** four times.
- Click **Enregistrer tout** (two-file transaction), re-open the saved JSON
  pair and start the edited mission with the real `GameSession`.
- Confirm the canonical Player observes identical bridge placement, actor
  name, switch target and event condition, before/after every history action.
- Ensure no Tk callback exceptions and no pending Save All recovery marker.

## Crash-restart recovery

Simulate an unsaved Content + GameProject draft from the existing
`EditRecoveryJournal`. Launch Tk, **explicitly accept** the recovery
dialog and verify that both saved files stay byte-for-byte unchanged until
the user presses **Enregistrer tout**. Verify restoration of the JSON editor,
project title and two-file save.

## Test commands

```sh
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest \
  tests_standalone.test_editor_r1_gui_gate -v
```

This gate is wired as an explicit step in
`.github/workflows/standalone.yml`'s `editor` job.

### Boundary and remaining acceptance

This test operates through the **actual native JSON editor** and the existing
Tk history/save controls. It does not yet certify drag-and-drop, visual
structure selection, entity property inspector gestures, event graph canvas,
focus order or tile-by-tile drawing. Those require a separate visual interaction
gate; do not classify this test alone as a complete visual-editing certification.

The test introduces no new schema, no alternative GameProject/Content model,
and no Tk import in the command core.
