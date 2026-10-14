# Studio Workspace Layout — UI refactor (2026-10-14)

## Why

The old Tk Studio stacked an eleven-button toolbar, a four-page global tool
notebook, a separate floor-editing toolbar, a growing horizontal editor
notebook, and a right column mixing inspector, groups, prefabs and generation.
At typical desktop widths the editor tab labels were truncated and the actual
editing surface competed with controls from unrelated workflows.

## New navigation (no editor reimplementation)

- The top header exposes **Fichier** (all previous file/game actions), direct
  Save, Undo/Redo and Edit/Playtest actions.
- Seven thematic workspaces (**Carte & monde**, **Contenu**, **Événements**,
  **Campagne**, **Présentation**, **Analyse**, **Projet**) and an **Autres**
  fallback replace the always-visible row of dozens of editor tabs.
- The **Vue** selector lists only the pages belonging to the current family.
  Existing Notebook frame identities and `notebook.select()` calls are
  unchanged. Any direct jump from Workspace, Problems, graph editors,
  shortcuts or saved layout updates the active category and view selector.
- The **Onglets** checkbox restores the native Tk notebook tabs if needed.
- The four contextual map tool pages are visible only on **Carte et combat**;
  floor editing is now in **Architecture** rather than global.
- The existing right map dock has three tabs: **Inspecteur** (minimap +
  selection details), **Groupes**, **Préfabs** (scrollable, includes assisted
  quarter generation). No authoring action or command has changed.
- Human **Playtest Lab** starts with import guidance instead of empty table,
  graph and detail areas. Once imported, sessions and duration chart sit side by
  side above a resizable inspection area; chart redraw on resize preserves
  the selected session.

## Functional constraints

No modification to `Content`, `GameProject`, `GameSession`, source JSON,
undo/redo history, authored battle rules, rendering transforms or persisted
workspace layout fields. The existing direct per-editor links remain active.

## Verification

Run headless classification tests:

    python -m unittest tests_standalone.test_studio_layout_2026 -v

Run real-Tk smoke checks under Xvfb (Linux):

    SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
        tests_standalone.test_studio_layout_2026 \
        tests_standalone.test_playtest_384_gui -v

Manual gate at 1280×800 and 1662×896:

1. Verify the family buttons never truncate into dozens of individual tabs.
2. Switch Carte → Analyse/Playtest → Projet and back. Map toolstrip must appear
   only on Carte; selections are preserved and the canvas still handles input.
3. From Problems or Workspace navigate to a specific editor or map tile:
   category, view selector and target must remain synchronized.
4. Inspector must be visible without scrolling past prefab generation;
   group and prefab actions remain accessible in their respective tabs.
5. Expand the prefab library until scroll is needed; minimap and inspector
   must remain responsive; import a valid playtest to reveal data panels.
6. Save layout, close, reopen, and confirm the last editor and sash positions
   restore; use the **Onglets** checkbox as a native-tabs fallback.
7. Verify Undo/Redo, Map playtest, create floor, prefab placement and mission
   switching preserve their original behavior.

## Follow-up — adaptive shell and focused map workflow

- At widths below 1280 px, the thematic section buttons collapse into a
  single category selector; the **Vue** selector still targets the existing
  editor tabs. The controls expand automatically on larger windows.
- **Affichage** allows independent toggle of Explorateur, Inspecteur and
  Journal. Shortcut keys (while on the map): **Ctrl+B**, **Ctrl+Alt+I**,
  **Ctrl+J**. **F11** enters/exits map focus; previously hidden panes stay
  hidden when leaving focus. The actual tactical Canvas never gets recreated.
- Dock visibility is stored atomically in the UI-only sidecar
  `*.workspace.docks.json`, never inside `Content`, `GameProject` or game
  saves. The existing sash positions continue in `*.workspace.layout.json`.
  An invalid or missing dock sidecar safely restores the default visibility.
- The map command bar is context-sensitive: mission / brush / terrain in edit
  mode, unit / command / turn in playtest. The isometric 2.5D switch is directly
  visible without opening the terrain subtab.
- New tests cover corrupted or untrusted dock preference values, atomic file
  writes, focus restoration and the same existing child-frame identities.

Follow-up checks:

    python -m unittest tests_standalone.test_studio_docks_2026 -v
    SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
        tests_standalone.test_studio_docks_2026 -v

At 1280x800 ensure the category selector appears and at 1662x896 the
category strip reappears. Toggle each dock and F11 repeatedly, then reopen
the Studio and verify sizes and visibility. Start/stop a playtest and confirm
that battle commands replace map-brush controls rather than stacking.
