# B1.1 — Building Editor Reliability

## Source

Follow-up to Building Editor 1.0 (PR #204). This tranche changes UI
navigation and integration tests only, not the building data model.

## Correctness fixes

- Entering **Bâtiments** during an active Player/Studio playtest is refused;
  it cannot replace or hide the combat toolbar, cancel a battle or change the
  active session. The current top navigation is restored.
- While the JSON source view contains pending changes, building mutation
  buttons are disabled. Canonical authoring commands still independently
  enforce the same preconditions.
- The Building editor is a **mode** of the existing map tab. External
  `notebook.select()` navigation must deactivate the Building mode and
  correctly restore the current navigation family.
- Empty selections disable facade/window/level mutations. A compatible
  selected building enables only its applicable actions.

## Tk and CI tests

```sh
python3 -m unittest tests_standalone.test_studio_layout_2026 -v

SPOREBOUND_GUI_SMOKE=1 xvfb-run -a -s "-screen 0 1600x900x24" \
    python3 -m unittest \
    tests_standalone.test_studio_layout_2026 \
    tests_standalone.test_map_builder4_3732b_gui -v
```

The new `editor` workflow gate exercises real tkinter widgets before
legacy prefab flows, asserting the context states, menu routing, map Canvas
visibility, facade/window authoring and save.

Older GUI tests now call **Fichier → Enregistrer sous…** through the
shared `tests_standalone/studio_gui_actions.py` helper, rather than
looking for the removed `ttk.Button('Enregistrer sous')`.

## Manual approval checklist

1. Open an empty map, choose Bâtiments: no inappropriate mutation available.
2. Place and select a house; confirm General/Extérieur/Intérieur tab visibility.
3. Edit facade and window; save/reload; verify undo and redo.
4. Switch Bâtiments → Projet → Carte and Bâtiments → Evénements → Carte.
5. Start a playtest and try Bâtiments: combat state and toolbar unchanged.
6. Edit raw JSON without applying; structure commands cannot bypass pending source.
7. Verify 1280×720 display and high-DPI scrollability on Windows and Linux.

## Out of scope

Building Builder direct 2.5D manipulation (B1.2), interior overhaul (B1.3),
and unrelated failing standalone rules tests. Those remain separately gated.
