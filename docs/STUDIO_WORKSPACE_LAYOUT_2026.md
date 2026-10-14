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
